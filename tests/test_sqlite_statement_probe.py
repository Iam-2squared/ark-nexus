"""Additive bounded synthetic SQL/native evidence, independent of frozen suites."""

import ctypes
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexus import sqlite_probe
from nexus._sqlite_vfs_probe import Observer, runtime_library
from nexus.sqlite_workload import ProbeProblem, logical_digest, run_statements, run_workload
from nexus.sqlite_workload import seed_database as seed

CHECKOUT = Path(__file__).absolute().parents[1]


@pytest.mark.parametrize("mode", ["delete", "wal"])
def test_late_statement_abort_retains_prior_write_fts_fk_hash_and_restored_snapshot(tmp_path, mode):
    store = seed(tmp_path / "source" / "synthetic.sqlite3", 1024)
    with closing(sqlite3.connect(store.path)) as db:
        report = run_statements(db, 1024, mode)
        original = logical_digest(db)
        assert report["temp_store"] == 2
        assert report["journal_mode"] == mode
        assert report["interrupted_transaction_rollback"] is True
        assert report["temp_sort_rows"] == 1024
        assert len(report["cases"]) == 3
        assert all(case["partial_row_callbacks"] == 1023
                   and case["prior_transaction_write_retained"]
                   and case["statement_rollback"] and case["stored_integrity"]
                   for case in report["cases"])
        assert db.execute("SELECT count(*) FROM projects").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1024
        assert logical_digest(db) == original
    assert store.integrity_report()["ok"] is True


def test_workload_uses_new_backups_and_preserves_all_logical_tables(tmp_path):
    report = run_workload(tmp_path / "new-workload", rows=64)
    assert report["status"] == "synthetic_PASS"
    assert report["storage_location_qualified"] is False
    assert report["private_import_allowed"] is False
    assert len(report["workloads"]) == 2
    assert all(part["backup_restore_logical_equal"] for part in report["workloads"])
    with pytest.raises(ProbeProblem):
        run_workload(tmp_path / "new-workload", rows=64)


@pytest.mark.parametrize("rows", [True, 0, 31, 8193, 50000, "2048", None])
def test_unbounded_or_coerced_workloads_are_refused_before_creation(tmp_path, rows):
    path = tmp_path / "must-not-exist"
    with pytest.raises(ProbeProblem):
        run_workload(path, rows=rows)
    assert not path.exists()


@pytest.mark.parametrize("mode", ["off", "memory", "persist", "truncate", "DELETE", None])
def test_unsafe_or_unknown_journal_choices_are_never_accepted(tmp_path, mode):
    store = seed(tmp_path / "source" / "synthetic.sqlite3", 32)
    with closing(sqlite3.connect(store.path)) as db, pytest.raises(ProbeProblem):
        run_statements(db, 32, mode)


def test_runtime_evidence_is_path_free_and_does_not_change_parent_temp_environment():
    names = ("SQLITE_TMPDIR", "TMPDIR", "TMP", "TEMP")
    before = {name: os.environ.get(name) for name in names}
    report = sqlite_probe.runtime_info()
    assert report["temp_store"] == 2
    assert report["sqlite_version"] == sqlite3.sqlite_version
    assert report["extension_kind"] in ("builtin", "dynamic_module")
    assert report["module_absolute_path_recorded"] is False
    assert {name: os.environ.get(name) for name in names} == before
    serialized = json.dumps(report)
    assert str(CHECKOUT) not in serialized
    assert not any("/" in option or "\\" in option for option in report["compile_options"])


@pytest.mark.parametrize("kind", ["outside", "tmp-root", "dotdot", "existing"])
def test_probe_requires_a_new_literal_checkout_local_root_before_io(tmp_path, kind):
    allowed = CHECKOUT / "tmp"
    candidate = {
        "outside": CHECKOUT / ("synthetic-refused-" + uuid.uuid4().hex), "tmp-root": allowed,
        "dotdot": allowed / ".." / "outside",
        "existing": allowed,
    }[kind]
    with pytest.raises(ProbeProblem):
        sqlite_probe.run_probe(candidate, rows=32)
    if kind == "outside":
        assert not candidate.exists()


@pytest.mark.parametrize("source", [True, "A" * 40, "a" * 39, "synthetic-secret-path"])
def test_source_head_must_be_explicit_valid_revision_without_echo(source):
    root = CHECKOUT / "tmp" / "sqlite-test-evidence" / uuid.uuid4().hex
    with pytest.raises(ProbeProblem) as caught:
        sqlite_probe.run_probe(root, rows=32, source_head=source)
    assert str(source) not in str(caught.value)
    assert not root.exists()


def test_disposable_native_probe_is_honest_and_keeps_defaults_parent_env_and_public_scope():
    root = CHECKOUT / "tmp" / "sqlite-test-evidence" / uuid.uuid4().hex
    names = ("SQLITE_TMPDIR", "TMPDIR", "TMP", "TEMP")
    before = {name: os.environ.get(name) for name in names}
    report = sqlite_probe.run_probe(root, rows=64, source_head="a" * 40)
    assert report["repository"] == "Iam-2squared/ark-nexus"
    assert report["source_head"] == "a" * 40
    assert report["official_v1"] == "BLOCKED"
    assert report["private_import_allowed"] is False
    assert {name: os.environ.get(name) for name in names} == before
    native = report["native"]
    assert native["default_vfs_changed"] is False
    assert native["alternate_sqlite_loaded"] is False
    if native["captured"]:
        assert native["status"] == "synthetic_PASS"
        assert native["runtime_binding"] == "python_sqlite3_vfs_reached"
        assert native["callback_errors"] == native["named_outside_private_count"] == 0
        assert native["os_syscalls_captured"] is False
        assert native["physical_unnamed_paths_qualified"] is False
        assert native["backup_connections_captured"] is False
        for mode in ("delete", "wal"):
            assert native["counts"][f"{mode}.main_db.open"] == 1
            assert native["counts"][f"{mode}.main_db.write_calls"] > 0
    else:
        assert native == {"status": "NOT RUN", "captured": False,
                          "reason": "capability_unavailable", "native_registration_count": 0,
                          "alternate_sqlite_loaded": False, "default_vfs_changed": False,
                          "private_import_allowed": False}
    assert str(root) not in json.dumps(report)
    assert "Synthetic payload" not in json.dumps(report)


@pytest.mark.parametrize("failure", ["timeout", "crash", "invalid-json", "oversize"])
def test_child_failures_are_fixed_and_do_not_claim_capture(monkeypatch, tmp_path, failure):
    def failed(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("synthetic-private-path", 60)
        output = b"synthetic-private-marker" if failure == "invalid-json" else b"x" * 65537
        return subprocess.CompletedProcess(args=[], returncode=1 if failure == "crash" else 0,
                                           stdout=output)

    monkeypatch.setattr(sqlite_probe.subprocess, "run", failed)
    with pytest.raises(ProbeProblem) as caught:
        sqlite_probe.native_subprocess(tmp_path, 32)
    assert "synthetic-private" not in str(caught.value)


def test_internal_child_cannot_run_without_isolated_environment():
    root = CHECKOUT / "tmp" / "sqlite-child-test" / uuid.uuid4().hex
    root.mkdir(mode=0o700, parents=True)
    (root / "native-temp").mkdir(mode=0o700)
    result = subprocess.run(
        [sys.executable, "-m", "nexus.sqlite_probe", "--native-child", "--root", str(root)],
        cwd=CHECKOUT, capture_output=True, timeout=10,
    )
    assert result.returncode == 1
    assert str(root).encode() not in result.stderr
    assert b"Traceback" not in result.stderr
    assert not (root / "observed-workload").exists()


def test_probe_cli_invalid_arguments_are_redacted():
    result = subprocess.run(
        [sys.executable, "-m", "nexus.sqlite_probe", "--unknown", "synthetic-private-key"],
        cwd=CHECKOUT, capture_output=True, timeout=10,
    )
    assert result.returncode == 2
    assert b"synthetic-private-key" not in result.stdout + result.stderr
    assert b"Traceback" not in result.stderr


def test_vfs_named_paths_are_limited_without_opening_or_deleting_them(tmp_path):
    observer = object.__new__(Observer)
    observer.root = tmp_path
    for name, expected in ((str(tmp_path / "synthetic.sqlite3"), True),
                           (str(tmp_path / ".." / "outside.sqlite3"), False),
                           (str(tmp_path.parent / "outside.sqlite3"), False)):
        buffer = ctypes.create_string_buffer(os.fsencode(name))
        assert observer.path_inside(ctypes.addressof(buffer)) is expected
    assert observer.path_inside(None) is False
    assert list(tmp_path.iterdir()) == []


def test_missing_native_exports_use_capability_classification(monkeypatch):
    from nexus import _sqlite_vfs_probe as probe

    monkeypatch.setattr(probe._sqlite3, "__file__", None, raising=False)
    monkeypatch.setattr(probe.ct, "CDLL", lambda _name: object())
    monkeypatch.setattr(probe.ct, "WinDLL",
                        lambda *args, **kwargs: SimpleNamespace(GetModuleHandleW=lambda name: None),
                        raising=False)
    with pytest.raises(probe.Unavailable):
        runtime_library()


@pytest.mark.parametrize("payload", [
    b'{"status":"NOT RUN","captured":false,"reason":"capability_unavailable",'
    b'"native_registration_count":0,"alternate_sqlite_loaded":false,'
    b'"default_vfs_changed":false,"private_import_allowed":false,'
    b'"raw_key":"PRIVATE-SYNTHETIC-ONLY"}',
    b'{"status":"NOT RUN","captured":false,"reason":"capability_unavailable",'
    b'"native_registration_count":0,"alternate_sqlite_loaded":false,'
    b'"default_vfs_changed":false,"private_import_allowed":false,"captured":true}',
    b'{"status":"synthetic_PASS","captured":true,"private_import_allowed":false,'
    b'"workload":{"content":"PRIVATE-SYNTHETIC-ONLY"}}',
    b'{"status":"synthetic_PASS","captured":true,"private_import_allowed":false}',
], ids=["unknown-secret-field", "duplicate-contradiction", "nested-secret", "missing-schema"])
def test_child_evidence_cannot_forward_unknown_secret_fields_or_collapsed_duplicates(
    monkeypatch, tmp_path, payload,
):
    monkeypatch.setattr(sqlite_probe.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args=[], returncode=0, stdout=payload))
    with pytest.raises(ProbeProblem) as caught:
        sqlite_probe.native_subprocess(tmp_path, 32)
    assert "PRIVATE-SYNTHETIC-ONLY" not in str(caught.value)
