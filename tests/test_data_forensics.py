"""Count-only observer and fresh-root guards; no recursive full-suite subprocess."""

import json
import os
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from nexus import data_forensics as forensic
from nexus.store import Store


def watched_store(tmp_path):
    base = tmp_path / "dedicated-pytest"
    path = base / "test_10000_message_reimport_an0" / "nexus.sqlite3"
    store = Store(path)
    return store, forensic.CountObserver(base)


def minimal_case():
    point = {
        "sequence": 1, "connection": 0, "phase": "final", "readonly_observer": True,
        "file_identity_same": True, "sidecars_present": {"journal": False, "wal": False,
                                                          "shm": False},
        "counts": {"source_instances": 1, "conversations": 100, "messages": 10_000,
                   "import_batches": 2, "message_search": 10_000, "source_events": 2,
                   "audit_log": 2, "schema_migrations": 2},
        "foreign_key_errors": 0, "foreign_keys_enabled": False, "temp_store": 2,
        "journal_mode": "delete", "in_transaction": True, "total_changes": 0,
    }
    return {
        "schema": 1, "scope": "single", "observed": True,
        "runtime": {"python": "3.12.14", "sqlite": "3.53.1", "os": "Linux",
                    "sqlite_module": "builtin", "connection_runtime": "current_python_sqlite3"},
        "exit_code": 0, "pytest": {"passed": 1, "failed": 0, "skipped": 0, "errors": 0},
        "frozen_test": "PASS", "connections": 1, "explicit_factories_respected": 0,
        "checkpoint_limit_reached": False, "observation_errors": 0,
        "prepared_core_deletes": 0, "prepared_core_drops": 0, "timeline": [point],
    }


def fake_metadata(monkeypatch):
    monkeypatch.setattr(forensic, "workspace_metadata", lambda _repo: ("a" * 40, False))
    monkeypatch.setattr(forensic, "_frozen_definition", lambda: "b" * 64)


def fresh_root():
    import uuid

    return forensic.CHECKOUT_ROOT / "tmp" / "forensics-unit" / uuid.uuid4().hex


def test_observer_commit_rollback_close_counts_are_readonly_and_do_not_change_parent(tmp_path):
    store, observer = watched_store(tmp_path)
    original_connect = sqlite3.connect
    original_environment = os.environ.copy()
    connection = observer.connect(store.path.as_uri() + "?mode=rw", uri=True)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO projects(id,name) VALUES (?,?)",
                       ("SYNTHETIC-ID-NOT-IN-EVIDENCE", "SYNTHETIC-TEXT-NOT-IN-EVIDENCE"))
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("DELETE FROM projects")
    connection.rollback()
    connection.close()
    observer.final()
    assert sqlite3.connect is original_connect
    assert os.environ == original_environment
    assert observer.observation_errors == 0
    assert observer.prepared_deletes == 0  # Projects are outside the watched 10k core.
    phases = [point["phase"] for point in observer.timeline]
    assert {"commit_before", "commit_after", "rollback_before", "rollback_after",
            "close_before", "close_reopened", "final"} <= set(phases)
    assert all(point["file_identity_same"] for point in observer.timeline)
    with sqlite3.connect(store.path) as verified:
        assert verified.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
    evidence = json.dumps(observer.timeline)
    assert "SYNTHETIC-ID-NOT-IN-EVIDENCE" not in evidence
    assert "SYNTHETIC-TEXT-NOT-IN-EVIDENCE" not in evidence
    assert str(store.path) not in evidence


def test_observer_reads_uncommitted_counts_then_reports_only_statement_rollback(tmp_path):
    store, observer = watched_store(tmp_path)
    connection = observer.connect(store.path)
    connection.execute("BEGIN")
    connection.execute("INSERT INTO audit_log(id,action,actor,target,outcome,at) "
                       "VALUES('synthetic-first','synthetic','synthetic','synthetic','synthetic','x')")
    connection.commit()
    connection.execute("BEGIN")
    connection.execute("INSERT INTO audit_log(id,action,actor,target,outcome,at) "
                       "VALUES('synthetic-second','synthetic','synthetic','synthetic','synthetic','x')")
    connection.rollback()
    connection.close()
    before = [point for point in observer.timeline if point["phase"] == "rollback_before"][-1]
    after = [point for point in observer.timeline if point["phase"] == "rollback_after"][-1]
    reopened = [point for point in observer.timeline if point["phase"] == "close_reopened"][-1]
    assert before["counts"]["audit_log"] == 2
    assert after["counts"]["audit_log"] == reopened["counts"]["audit_log"] == 1
    assert before["in_transaction"] is True
    assert after["in_transaction"] is False


def test_observer_never_overrides_explicit_connection_factory(tmp_path):
    store, observer = watched_store(tmp_path)

    class ExistingFactory(sqlite3.Connection):
        pass

    connection = observer.connect(store.path, factory=ExistingFactory)
    assert type(connection) is ExistingFactory
    connection.close()
    assert observer.explicit_factories == 1
    assert observer.connections == 0
    assert observer.timeline == []


def test_observer_other_database_has_exact_original_connection_class(tmp_path):
    _store, observer = watched_store(tmp_path)
    connection = observer.connect(tmp_path / "unwatched.sqlite3")
    assert type(connection) is sqlite3.Connection
    connection.close()
    assert observer.connections == 0


def test_observer_preserves_legacy_positional_factory_and_uri(tmp_path):
    store, observer = watched_store(tmp_path)

    class ExistingFactory(sqlite3.Connection):
        pass

    connection = observer.connect(store.path.as_uri() + "?mode=rw", 15, 0, None, True,
                                  ExistingFactory, 128, True)
    assert type(connection) is ExistingFactory
    connection.close()
    assert observer.explicit_factories == 1
    assert observer.connections == 0


def test_readonly_final_does_not_recreate_missing_watched_database(tmp_path):
    store, observer = watched_store(tmp_path)
    observer.connect(store.path).close()
    held = store.path.with_name("held-synthetic.sqlite3")
    store.path.rename(held)
    observer.final()
    assert not store.path.exists()
    assert held.is_file()
    assert observer.observation_errors == 1


def test_observer_file_replacement_is_anonymous_failure_and_preserves_both_files(tmp_path):
    store, observer = watched_store(tmp_path)
    observer.connect(store.path).close()
    held = store.path.with_name("held-synthetic.sqlite3")
    store.path.rename(held)
    replacement = Store(store.path)
    observer.final()
    final = observer.timeline[-1]
    assert final["phase"] == "final"
    assert final["file_identity_same"] is False
    assert held.is_file() and replacement.path.is_file()
    assert str(held) not in json.dumps(final)


def test_unobserved_discovery_ignores_pytest_current_link_alias(tmp_path, monkeypatch):
    store, observer = watched_store(tmp_path)
    alias = observer.basetemp / "test_10000_message_reimport_ancurrent"
    # Portable link classification: no symlink privileges or OS settings required.
    alias.mkdir()
    (alias / "nexus.sqlite3").write_bytes(store.path.read_bytes())
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == alias or original(path))
    observer.final()
    assert len(observer.timeline) == 1
    assert observer.timeline[0]["phase"] == "final"
    assert observer.path == store.path


def test_unobserved_discovery_rejects_junction_before_reading_target(tmp_path, monkeypatch):
    store, observer = watched_store(tmp_path)
    alias = observer.basetemp / "test_10000_message_reimport_ancurrent"
    alias.mkdir()
    (alias / "nexus.sqlite3").write_bytes(store.path.read_bytes())
    original_junction = Path.is_junction
    original_directory = Path.is_dir
    monkeypatch.setattr(Path, "is_junction", lambda path: path == alias or original_junction(path))

    def is_directory(path):
        if path == alias:
            pytest.fail("junction target must not be followed")
        return original_directory(path)

    monkeypatch.setattr(Path, "is_dir", is_directory)
    observer.final()
    assert observer.path == store.path
    assert observer.timeline[-1]["phase"] == "final"


def test_zero_file_identity_is_refused_without_creating_or_repairing_database(tmp_path, monkeypatch):
    store, observer = watched_store(tmp_path)
    original = Path.stat

    class ZeroIdentity:
        def __init__(self, metadata):
            self.metadata = metadata
            self.st_ino = 0

        def __getattr__(self, name):
            return getattr(self.metadata, name)

    def stat(path, *args, **kwargs):
        metadata = original(path, *args, **kwargs)
        return ZeroIdentity(metadata) if path == store.path else metadata

    monkeypatch.setattr(Path, "stat", stat)
    with pytest.raises(forensic.ForensicsProblem, match="identity unavailable"):
        observer.final()
    assert store.path.is_file()
    assert observer.timeline == []


def test_authorizer_counts_preparations_without_forbidding_or_logging_sql(tmp_path):
    store, observer = watched_store(tmp_path)
    connection = observer.connect(store.path)
    connection.execute("DELETE FROM audit_log WHERE action=?", ("PRIVATE-SYNTHETIC-MARKER",))
    connection.execute("DROP TABLE audit_log")
    connection.commit()
    connection.close()
    assert observer.prepared_deletes >= 1
    assert observer.prepared_drops == 1
    assert "PRIVATE-SYNTHETIC-MARKER" not in json.dumps(observer.timeline)


def test_observer_checkpoint_cap_is_reported_instead_of_unbounded_growth(tmp_path, monkeypatch):
    store, observer = watched_store(tmp_path)
    monkeypatch.setattr(forensic, "MAX_CHECKPOINTS", 2)
    connection = observer.connect(store.path)
    connection.commit()
    connection.close()
    assert len(observer.timeline) == 2
    assert observer.capped is True


def test_case_allowlist_accepts_counts_only_and_never_marks_historical_issue_fixed():
    report = minimal_case()
    assert forensic.validate_case(report) == report
    assert all(forensic.comparison_checks(report).values())


@pytest.mark.parametrize("mutate", [
    lambda report: report.update({"private_path": "/PRIVATE-SYNTHETIC-MARKER"}),
    lambda report: report["runtime"].update({"module_path": "/PRIVATE-SYNTHETIC-MARKER"}),
    lambda report: report["runtime"].update({"sqlite": "PRIVATE-SYNTHETIC-MARKER"}),
    lambda report: report.update({"connections": True}),
    lambda report: report["pytest"].update({"passed": False}),
    lambda report: report["timeline"][0]["counts"].update({"messages": "PRIVATE-SYNTHETIC-MARKER"}),
    lambda report: report["timeline"][0].update({"file_identity_same": 1}),
    lambda report: report["timeline"][0].update({"phase": "PRIVATE-SYNTHETIC-MARKER"}),
    lambda report: report["timeline"][0]["sidecars_present"].update({"private": False}),
])
def test_case_allowlist_rejects_extra_fields_wrong_types_or_private_strings(mutate):
    report = minimal_case()
    mutate(report)
    with pytest.raises(forensic.ForensicsProblem) as raised:
        forensic.validate_case(report)
    assert "PRIVATE-SYNTHETIC-MARKER" not in str(raised.value)


def test_case_reader_refuses_duplicate_keys_and_does_not_echo_values(tmp_path):
    path = tmp_path / "case.json"
    path.write_text('{"scope":"single","scope":"PRIVATE-SYNTHETIC-MARKER"}', encoding="utf-8")
    with pytest.raises(forensic.ForensicsProblem) as raised:
        forensic._load_case(path)
    assert "PRIVATE-SYNTHETIC-MARKER" not in str(raised.value)


def test_post_close_discrepancy_is_detected_even_when_test_exit_says_pass():
    report = minimal_case()
    before = deepcopy(report["timeline"][0])
    before.update({"phase": "close_before", "connection": 1, "in_transaction": False})
    after = deepcopy(before)
    after.update({"phase": "close_reopened", "readonly_observer": True})
    after["counts"]["messages"] = 0
    report["timeline"][:0] = [before, after]
    assert forensic.comparison_checks(report)["committed_close_counts_equal"] is False
    report["timeline"][-1]["counts"]["source_instances"] = 0
    report["timeline"][-1]["foreign_key_errors"] = 2
    checks = forensic.comparison_checks(report)
    assert checks["final_expected_counts"] is False
    assert checks["foreign_keys_clean"] is False


@pytest.mark.parametrize("options", [
    {"trials": True}, {"trials": 0}, {"trials": 4}, {"child_timeout": 9},
    {"child_timeout": 181}, {"scopes": ()}, {"scopes": ("single", "single")},
    {"scopes": ("unknown",)}, {"scopes": ([],)},
    {"source_head": "PRIVATE-SYNTHETIC-MARKER"},
])
def test_invalid_bounds_fail_before_creating_root(options):
    root = fresh_root()
    with pytest.raises(forensic.ForensicsProblem) as raised:
        forensic.run_forensics(root, **options)
    assert not root.exists()
    assert "PRIVATE-SYNTHETIC-MARKER" not in str(raised.value)


def test_existing_root_is_refused_without_removing_synthetic_evidence(tmp_path):
    root = fresh_root()
    root.mkdir(parents=True)
    sentinel = root / "existing-synthetic"
    sentinel.write_bytes(b"synthetic evidence remains")
    with pytest.raises(forensic.ForensicsProblem):
        forensic.run_forensics(root)
    assert sentinel.read_bytes() == b"synthetic evidence remains"


def test_outside_root_and_parent_traversal_are_refused_before_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(forensic, "_run_case", lambda *_args: pytest.fail("child must not start"))
    for root in (forensic.CHECKOUT_ROOT.parent / "outside-forensics", forensic.CHECKOUT_ROOT / "tmp",
                 forensic.CHECKOUT_ROOT / "tmp" / ".." / "outside-forensics"):
        with pytest.raises(forensic.ForensicsProblem):
            forensic.run_forensics(root)


def test_finite_scope_reports_leave_historic_gate_open_and_do_not_reuse_paths(monkeypatch):
    fake_metadata(monkeypatch)
    root = fresh_root()
    calls = []

    def case(path, scope, observed, timeout):
        assert not path.exists()
        calls.append((path, scope, observed, timeout))
        path.mkdir()
        return {"status": "PASS", "reason": "synthetic_comparison_passed",
                "checks": {"final_expected_counts": True}, "evidence": None}

    monkeypatch.setattr(forensic, "_run_case", case)
    before_environment = os.environ.copy()
    report = forensic.run_forensics(root, trials=2, source_head="c" * 40)
    assert len(calls) == len(set(path for path, *_ in calls)) == 6
    assert [scope for _, scope, *_ in calls] == ["single", "single", "related", "related",
                                               "full", "full"]
    assert report["checkout_head"] == "a" * 40
    assert report["source_head"] == "c" * 40
    assert report["historical_10k"] == {
        "status": "OPEN", "gate": "BLOCKED", "root_cause_resolved": False,
        "reason": "not_reproduced_root_cause_unresolved"}
    assert report["official_v1"] == "BLOCKED"
    assert report["conditions"]["observer_affects_timing"] is True
    assert os.environ == before_environment
    assert json.loads((root / "report.json").read_text()) == report


def test_failure_report_retains_failed_case_and_historical_blocked_status(monkeypatch):
    fake_metadata(monkeypatch)
    root = fresh_root()

    def case(path, *_args):
        path.mkdir()
        (path / "synthetic-retained-evidence").write_bytes(b"retained")
        return {"status": "FAIL", "reason": "child_timeout", "evidence": None}

    monkeypatch.setattr(forensic, "_run_case", case)
    report = forensic.run_forensics(root, scopes=("single",), observed=False)
    assert report["result"] == "synthetic_comparison_failed"
    assert report["historical_10k"]["root_cause_resolved"] is False
    assert (root / "case-001" / "synthetic-retained-evidence").read_bytes() == b"retained"


def test_pr_checkout_does_not_invent_source_sha(monkeypatch):
    fake_metadata(monkeypatch)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setattr(forensic, "_run_case", lambda *_args: {
        "status": "PASS", "reason": "synthetic_comparison_passed", "evidence": None})
    report = forensic.run_forensics(fresh_root(), scopes=("single",))
    assert report["source_head"] is None
    assert report["source_declaration"] == "unavailable_pr_source"


def test_frozen_function_matches_checkout_without_editing_gate():
    assert len(forensic._frozen_definition()) == 64


def test_private_cli_argument_error_does_not_echo_value():
    result = subprocess.run([sys.executable, "-m", "nexus.data_forensics", "--trials",
                             "PRIVATE-SYNTHETIC-MARKER"], capture_output=True, timeout=10,
                            cwd=forensic.CHECKOUT_ROOT, check=False)
    assert result.returncode == 2
    assert b"PRIVATE-SYNTHETIC-MARKER" not in result.stdout + result.stderr
    assert result.stderr == b"Invalid command arguments. See --help for usage.\n"


def test_argv_scope_and_file_uri_classifier_do_not_confuse_unwatched_connections(tmp_path):
    _store, observer = watched_store(tmp_path)
    assert forensic._database_path(":memory:") is None
    assert forensic._database_path(b"private") is None
    assert forensic._database_path("file://remote/private.sqlite3", uri=True) is None
    target = observer.basetemp / "test_10000_message_reimport_an0" / "nexus.sqlite3"
    assert forensic._database_path(target.as_uri() + "?mode=ro", uri=True) == target
    assert not observer.watches(target.parent / "other.sqlite3")
    assert not observer.watches(Path(str(target) + "-wal"))
