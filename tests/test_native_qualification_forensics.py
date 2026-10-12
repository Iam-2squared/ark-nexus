"""Count-only native qualification and disposable observer lifetime regressions."""

import copy
import ctypes as ct
import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexus import _sqlite_vfs_probe as native
from nexus import sqlite_evidence
from nexus.sqlite_workload import ProbeProblem, run_backup_connections, run_workload


def fake_observer(root, *, close_result=0, methods_version=1, open_result=0):
    """Valid allocated C structs and Python callbacks; never a native registration."""
    calls = {"open": 0, "close": 0, "write": 0}

    @ct.CFUNCTYPE(ct.c_int, ct.c_void_p)
    def close(_file):
        calls["close"] += 1
        return close_result

    @ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int64)
    def write(_file, _buffer, _amount, _offset):
        calls["write"] += 1
        return 0

    methods = native.Methods()
    methods.iVersion = methods_version
    methods.xClose = ct.cast(close, ct.c_void_p).value
    methods.xWrite = ct.cast(write, ct.c_void_p).value

    @native.OPEN
    def open_file(_vfs, _name, file, _flags, _output_flags):
        calls["open"] += 1
        ct.cast(file, ct.POINTER(native.File)).contents.pMethods = ct.pointer(methods)
        return open_result

    @native.DELETE
    def delete(_vfs, _name, _sync):
        return 0

    original = native.VFS()
    original.iVersion = 3
    original.szOsFile = 128
    original.xOpen = ct.cast(open_file, ct.c_void_p).value
    original.xDelete = ct.cast(delete, ct.c_void_p).value
    library = SimpleNamespace(sqlite3_vfs_find=lambda name: None if name else ct.pointer(original))
    observer = native.Observer(library, root)
    # These allocated objects must outlive callbacks; the test never hands them to SQLite.
    observer.test_refs = (original, methods, open_file, close, write, delete)
    outer = ct.create_string_buffer(256)
    return observer, outer, calls


def open_fake(observer, outer):
    result = observer.open(None, None, ct.addressof(outer), native.KINDS["statement_journal"], None)
    methods = ct.cast(ct.addressof(outer), ct.POINTER(native.File)).contents.pMethods
    return result, methods


def in_thread(callback):
    result = []
    thread = threading.Thread(target=lambda: result.append(callback()))
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    return result[0]


def test_disposable_observer_refuses_open_on_another_thread_before_native_io(tmp_path):
    observer, outer, calls = fake_observer(tmp_path)
    result = in_thread(lambda: observer.open(
        None, None, ct.addressof(outer), native.KINDS["statement_journal"], None,
    ))
    assert result == 10
    assert calls["open"] == 0
    assert observer.callback_errors == 1
    assert not observer.files


def test_disposable_observer_refuses_write_on_another_thread_before_native_io(tmp_path):
    observer, outer, calls = fake_observer(tmp_path)
    result, methods = open_fake(observer, outer)
    assert result == 0
    write = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int64)(
        methods.contents.xWrite,
    )
    assert in_thread(lambda: write(ct.addressof(outer), None, 1, 0)) == 10
    assert calls["write"] == 0
    assert observer.callback_errors == 1
    close = ct.CFUNCTYPE(ct.c_int, ct.c_void_p)(methods.contents.xClose)
    assert close(ct.addressof(outer)) == 0
    assert not observer.files


def test_failed_native_close_is_an_observation_failure_even_when_handle_is_released(tmp_path):
    observer, outer, calls = fake_observer(tmp_path, close_result=10)
    result, methods = open_fake(observer, outer)
    assert result == 0
    close = ct.CFUNCTYPE(ct.c_int, ct.c_void_p)(methods.contents.xClose)
    assert close(ct.addressof(outer)) == 10
    assert calls["close"] == 1
    assert observer.callback_errors == 1
    assert not observer.files


def test_failed_open_with_methods_still_forwards_close_exactly_once(tmp_path):
    observer, outer, calls = fake_observer(tmp_path, open_result=14)
    result, methods = open_fake(observer, outer)
    assert result == 14 and methods
    close = ct.CFUNCTYPE(ct.c_int, ct.c_void_p)(methods.contents.xClose)
    assert close(ct.addressof(outer)) == 0
    assert calls["close"] == 1
    assert observer.callback_errors == 0
    assert not observer.files


def test_rejected_future_io_abi_closes_known_prefix_handle_without_installing_proxy(tmp_path):
    observer, outer, calls = fake_observer(tmp_path, methods_version=4)
    result, methods = open_fake(observer, outer)
    assert result == 10 and not methods
    assert calls["close"] == 1
    assert observer.callback_errors == 1
    assert not observer.files


def test_retained_callback_refuses_use_after_its_handle_closed(tmp_path):
    observer, outer, calls = fake_observer(tmp_path)
    result, methods = open_fake(observer, outer)
    assert result == 0
    write = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int64)(
        methods.contents.xWrite,
    )
    close = ct.CFUNCTYPE(ct.c_int, ct.c_void_p)(methods.contents.xClose)
    assert close(ct.addressof(outer)) == 0
    assert write(ct.addressof(outer), None, 1, 0) == 10
    assert close(ct.addressof(outer)) == 10
    assert calls["write"] == 0 and calls["close"] == 1
    assert observer.callback_errors == 2


@pytest.mark.parametrize("mismatch", ["version", "source-id"])
def test_exported_runtime_identity_mismatch_is_failure_not_missing_capability(monkeypatch, mismatch):
    import sqlite3

    class Function:
        def __init__(self, value):
            self.value = value

        def __call__(self, *args):
            return self.value

    library = SimpleNamespace(
        sqlite3_libversion=Function(b"0.0.0" if mismatch == "version"
                                    else sqlite3.sqlite_version.encode("ascii")),
        sqlite3_sourceid=Function(b"SYNTHETIC-MISMATCH-ONLY"),
        sqlite3_vfs_find=Function(None), sqlite3_vfs_register=Function(0),
        sqlite3_vfs_unregister=Function(0),
    )
    monkeypatch.setattr(native._sqlite3, "__file__", "synthetic-extension-only", raising=False)
    monkeypatch.setattr(native.ct, "CDLL", lambda *args, **kwargs: library)
    if hasattr(native.ct, "WinDLL"):
        monkeypatch.setattr(native.ct, "WinDLL", lambda *args, **kwargs:
                            SimpleNamespace(GetModuleHandleW=Function(None)))
    with pytest.raises(ProbeProblem) as caught:
        native.runtime_library()
    assert "SYNTHETIC-MISMATCH-ONLY" not in str(caught.value)


def test_existing_observer_name_is_failure_not_missing_native_capability(tmp_path):
    observer, _outer, _calls = fake_observer(tmp_path)
    library = SimpleNamespace(sqlite3_vfs_find=lambda name: observer.original)
    with pytest.raises(ProbeProblem):
        native.Observer(library, tmp_path)


@pytest.fixture(scope="module")
def native_report(tmp_path_factory):
    workload = run_workload(tmp_path_factory.mktemp("native-schema") / "source", rows=32)
    control = copy.deepcopy(workload)
    control["production_configuration"] = False
    control["statement_journal_open_count"] = 0
    for part in control["workloads"]:
        part["temp_store"] = 1
    return {
        "status": "synthetic_PASS", "captured": True, "reason": "vfs_capture_only",
        "runtime_binding": "python_sqlite3_vfs_reached",
        "native_origin": "python_extension_dependency", "native_registration_count": 1,
        "alternate_sqlite_loaded": False, "default_vfs_changed": False,
        "callback_errors": 0, "named_outside_private_count": 0, "unnamed_open_count": 0,
        "shm_callback_count": 0,
        "counts": {"delete.main_db.open": 1, "delete.main_db.write_calls": 1,
                   "delete.main_journal.write_calls": 1, "wal.main_db.open": 1,
                   "wal.main_db.write_calls": 1, "wal.wal.write_calls": 1,
                   "backup_delete.main_db.open": 2, "backup_delete.main_db.close": 2,
                   "backup_delete.main_db.write_calls": 1,
                   "backup_delete.main_db.readonly_open": 1,
                   "backup_delete.main_db.readwrite_open": 1,
                   "backup_wal.main_db.open": 2, "backup_wal.main_db.close": 2,
                   "backup_wal.main_db.write_calls": 1,
                   "backup_wal.main_db.readonly_open": 1,
                   "backup_wal.main_db.readwrite_open": 1},
        "workload": workload, "file_positive_control": control,
        "experimental_backup_capture": {
            "status": "synthetic_PASS", "actual_python_connections_captured": True,
            "production_backup_api_captured": False, "storage_location_qualified": False,
            "private_import_allowed": False, "workloads": [
                {"journal_mode": mode, "rows": 32, "logical_tables_compared": 13,
                 "source_readonly": True, "source_temp_store": 2, "destination_temp_store": 2,
                 "logical_tables_equal": True, "stored_integrity": True, "fts_query_equal": True,
                 "fts_internal_integrity": True}
                for mode in ("delete", "wal")
            ],
        },
        "os_syscalls_captured": False, "physical_unnamed_paths_qualified": False,
        "backup_connections_captured": False, "private_import_allowed": False,
    }


def with_gates(report):
    report["statement_journal_gates"] = sqlite_evidence.statement_journal_gates(
        report["counts"], file_control_supported=report["file_positive_control"]["status"]
        != "NOT RUN",
    )
    return report


def test_vfs_capture_without_positive_control_is_not_statement_qualification(native_report):
    report = with_gates(copy.deepcopy(native_report))
    sqlite_evidence.validate_native(report, 32)
    assert report["status"] == "synthetic_PASS"
    for gate in report["statement_journal_gates"].values():
        assert gate["status"] == "NOT RUN"
        assert gate["reason"] == "positive_control_not_observed"
        assert gate["positive_control_observed"] is False
        assert gate["storage_location_qualified"] is False
        assert gate["private_import_allowed"] is False


def test_file_wal_positive_control_cannot_qualify_unobserved_delete_control(native_report):
    report = copy.deepcopy(native_report)
    report["counts"].update({"file_control_wal.statement_journal.open": 2,
                             "file_control_wal.statement_journal.write_calls": 1968,
                             "file_control_wal.statement_journal.write_bytes": 4157400})
    report["file_positive_control"]["statement_journal_open_count"] = 2
    with_gates(report)
    sqlite_evidence.validate_native(report, 32)
    assert report["statement_journal_gates"]["delete"]["status"] == "NOT RUN"
    assert report["statement_journal_gates"]["wal"]["status"] == "synthetic_PASS"
    assert report["statement_journal_gates"]["wal"]["reason"] == (
        "positive_control_observed_memory_subjournal_absent"
    )


@pytest.mark.parametrize("counts", [
    {}, {"open": 1}, {"open": 1, "write_calls": 1}, {"open": 1, "write_bytes": 4096},
    {"write_calls": 1, "write_bytes": 4096},
])
def test_partial_file_control_cannot_promote_memory_zero_to_pass(counts):
    values = {"file_control_wal.statement_journal." + name: value
              for name, value in counts.items()}
    gate = sqlite_evidence.statement_journal_gates(values, file_control_supported=True)["wal"]
    assert gate["status"] == "NOT RUN"
    assert gate["positive_control_observed"] is False


@pytest.mark.parametrize("mode", ["delete", "wal"])
def test_memory_subjournal_observation_is_blocked_even_with_valid_positive_control(mode):
    counts = {f"file_control_{mode}.statement_journal.open": 1,
              f"file_control_{mode}.statement_journal.write_calls": 1,
              f"file_control_{mode}.statement_journal.write_bytes": 4096,
              f"{mode}.statement_journal.open": 1,
              f"{mode}.statement_journal.write_calls": 1,
              f"{mode}.statement_journal.write_bytes": 4096}
    gate = sqlite_evidence.statement_journal_gates(counts, file_control_supported=True)[mode]
    assert gate["status"] == "BLOCKED"
    assert gate["reason"] == "memory_subjournal_observed"
    assert gate["storage_location_qualified"] is False


def test_compiled_memory_only_control_remains_not_run(native_report):
    report = copy.deepcopy(native_report)
    report["file_positive_control"] = {"status": "NOT RUN", "reason": "compiled_memory_only"}
    with_gates(report)
    sqlite_evidence.validate_native(report, 32)
    assert all(gate["status"] == "NOT RUN" and gate["reason"] == "compiled_memory_only"
               for gate in report["statement_journal_gates"].values())


@pytest.mark.parametrize("field,value", [
    ("status", "synthetic_PASS"), ("reason", "positive_control_observed_memory_subjournal_absent"),
    ("positive_control_observed", True), ("file_control_write_calls", 1),
    ("memory_open_count", 1), ("storage_location_qualified", True),
    ("private_import_allowed", True), ("raw_path", "SYNTHETIC-PRIVATE-PATH-ONLY"),
])
def test_child_gate_cannot_forge_qualification_or_forward_private_fields(native_report, field, value):
    report = with_gates(copy.deepcopy(native_report))
    report["statement_journal_gates"]["wal"][field] = value
    with pytest.raises(ProbeProblem) as caught:
        sqlite_evidence.validate_native(report, 32)
    assert "SYNTHETIC-PRIVATE-PATH-ONLY" not in str(caught.value)
    assert str(Path.cwd()) not in json.dumps(report)


def source_digest(source_root):
    return tuple(hashlib.sha256((source_root / mode / "synthetic.sqlite3").read_bytes()).digest()
                 for mode in ("delete", "wal"))


def test_additional_observed_backup_connections_use_readonly_sources_and_new_destinations(tmp_path):
    source = tmp_path / "source"
    run_workload(source, rows=32)
    original = source_digest(source)
    flags = []

    def connection(path, *, readonly):
        flags.append(readonly)
        db = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True)
        if readonly:
            with pytest.raises(sqlite3.OperationalError):
                db.execute("DELETE FROM messages")
            db.rollback()
        return db

    report = run_backup_connections(tmp_path / "new-backup", source_root=source, rows=32,
                                    connection_factory=connection)
    assert flags == [True, False, True, False]
    assert source_digest(source) == original
    assert report["status"] == "synthetic_PASS"
    assert report["production_backup_api_captured"] is False
    assert report["storage_location_qualified"] is False
    assert report["private_import_allowed"] is False
    assert all(part["source_readonly"] and part["logical_tables_equal"]
               and part["fts_internal_integrity"] for part in report["workloads"])
    assert str(tmp_path) not in json.dumps(report)


@pytest.mark.parametrize("kind", ["existing", "source", "outside-sibling"])
def test_observed_backup_experiment_refuses_roots_without_touching_existing_files(tmp_path, kind):
    source = tmp_path / "source"
    run_workload(source, rows=32)
    original = source_digest(source)
    root = tmp_path / "new-backup"
    if kind == "existing":
        root.mkdir()
        (root / "synthetic-retained").write_bytes(b"Synthetic retained")
    elif kind == "source":
        root = source
    else:
        root = tmp_path / "other-parent" / "new-backup"
    with pytest.raises(ProbeProblem):
        run_backup_connections(root, source_root=source, rows=32,
                               connection_factory=lambda *args, **kwargs: pytest.fail("No IO"))
    assert source_digest(source) == original
    if kind == "existing":
        assert (root / "synthetic-retained").read_bytes() == b"Synthetic retained"
    elif kind == "outside-sibling":
        assert not root.exists()


def test_observed_backup_deadline_failure_preserves_readonly_source_and_has_fixed_diagnostic(
    tmp_path, monkeypatch,
):
    from nexus import sqlite_workload

    source = tmp_path / "source"
    run_workload(source, rows=32)
    original = source_digest(source)
    clock = iter((0, sqlite_workload.MAX_SECONDS + 1))
    monkeypatch.setattr(sqlite_workload.time, "monotonic", lambda: next(clock))

    def connection(path, *, readonly):
        return sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True)

    with pytest.raises(ProbeProblem) as caught:
        run_backup_connections(tmp_path / "interrupted", source_root=source, rows=32,
                               connection_factory=connection)
    assert source_digest(source) == original
    assert str(tmp_path) not in str(caught.value)
    for mode in ("delete", "wal"):
        with closing(connection(source / mode / "synthetic.sqlite3", readonly=True)) as db:
            assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 32


@pytest.mark.parametrize("failure", ["false-capture", "production-claim", "writable-source",
                                      "unknown-private-field", "missing-native-open", "missing-close",
                                      "missing-readonly-open", "missing-readwrite-open"])
def test_child_experimental_backup_requires_observed_connections_and_exact_scope(native_report, failure):
    report = with_gates(copy.deepcopy(native_report))
    backup = report["experimental_backup_capture"]
    if failure == "false-capture":
        backup["actual_python_connections_captured"] = False
    elif failure == "production-claim":
        backup["production_backup_api_captured"] = True
    elif failure == "writable-source":
        backup["workloads"][0]["source_readonly"] = False
    elif failure == "unknown-private-field":
        backup["workloads"][0]["raw_db"] = "SYNTHETIC-PRIVATE-DB-ONLY"
    elif failure == "missing-native-open":
        report["counts"]["backup_delete.main_db.open"] = 1
    elif failure == "missing-close":
        report["counts"].pop("backup_wal.main_db.close")
    elif failure == "missing-readonly-open":
        report["counts"]["backup_delete.main_db.readonly_open"] = 0
    else:
        report["counts"]["backup_wal.main_db.readwrite_open"] = 0
    with pytest.raises(ProbeProblem) as caught:
        sqlite_evidence.validate_native(report, 32)
    assert "SYNTHETIC-PRIVATE-DB-ONLY" not in str(caught.value)
