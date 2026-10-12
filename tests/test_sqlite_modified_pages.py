"""Additive modified-page DELETE workload and strict synthetic evidence."""

import copy

import pytest
from test_native_qualification_forensics import native_report as reference_native_fixture

from nexus import sqlite_evidence
from nexus.sqlite_workload import ProbeProblem, run_modified_pages_delete

native_report = reference_native_fixture


@pytest.fixture(scope="module")
def modified_report(tmp_path_factory, native_report):
    root = tmp_path_factory.mktemp("modified-pages-controls")
    report = copy.deepcopy(native_report)
    report["statement_journal_gates"] = sqlite_evidence.statement_journal_gates(
        report["counts"], file_control_supported=True)
    memory = run_modified_pages_delete(root / "memory", rows=32)
    file = run_modified_pages_delete(root / "file", rows=32, temp_store="file")
    for stage in ("predirty_memory_delete", "predirty_file_delete"):
        report["counts"].update({stage + ".main_db.open": 2, stage + ".main_db.close": 2,
                                 stage + ".main_db.write_calls": 1})
    report["counts"].update({"predirty_file_delete.statement_journal.open": 1,
                             "predirty_file_delete.statement_journal.write_calls": 1,
                             "predirty_file_delete.statement_journal.write_bytes": 1})
    report["modified_pages_delete_control"] = {
        "memory_workload": memory, "file_workload": file,
        "gate": sqlite_evidence.modified_pages_delete_gate(report["counts"], file_control_supported=True),
        "production_configuration": False, "storage_location_qualified": False,
        "private_import_allowed": False,
    }
    return report


def test_modified_pages_preserve_prior_update_statement_rollback_and_reopen(modified_report):
    sqlite_evidence.validate_native(modified_report, 32)
    for kind in ("memory_workload", "file_workload"):
        control = modified_report["modified_pages_delete_control"][kind]
        assert control["prior_rows_updated"] == 32 and control["partial_row_callbacks"] == 31
        assert control["statement_rollback"] and control["reopened_logical_equal"]
    assert modified_report["modified_pages_delete_control"]["gate"]["status"] == "synthetic_PASS"
    assert modified_report["statement_journal_gates"]["delete"]["status"] == "NOT RUN"


@pytest.mark.parametrize("change", [
    lambda r: r["modified_pages_delete_control"].update({"private_path": "PRIVATE-SYNTHETIC"}),
    lambda r: r["modified_pages_delete_control"].update({"file_workload": []}),
    lambda r: r["modified_pages_delete_control"].update({"production_configuration": True}),
    lambda r: r["modified_pages_delete_control"]["memory_workload"].update({"statement_rollback": False}),
    lambda r: r["modified_pages_delete_control"]["file_workload"].update({"partial_row_callbacks": True}),
    lambda r: r["modified_pages_delete_control"]["gate"].update({"positive_control_observed": 1}),
    lambda r: r["modified_pages_delete_control"]["gate"].update({"storage_location_qualified": True}),
    lambda r: r["counts"].update({"predirty_file_delete.statement_journal.write_calls": 0}),
    lambda r: r["counts"].update({"predirty_memory_delete.statement_journal.open": 1}),
    lambda r: r["counts"].update({"predirty_memory_delete.main_db.close": 1}),
])
def test_modified_control_cannot_forge_scope_counters_or_forward_private_fields(modified_report, change):
    report = copy.deepcopy(modified_report)
    change(report)
    with pytest.raises(ProbeProblem) as raised:
        sqlite_evidence.validate_native(report, 32)
    assert "PRIVATE-SYNTHETIC" not in str(raised.value)


@pytest.mark.parametrize("counts,supported,expected", [
    ({}, True, "NOT RUN"),
    ({"predirty_file_delete.statement_journal.open": 1}, True, "NOT RUN"),
    ({"predirty_memory_delete.statement_journal.open": 1}, True, "BLOCKED"),
    ({}, False, "NOT RUN"),
])
def test_modified_delete_qualification_needs_its_own_writing_positive_control(counts, supported, expected):
    gate = sqlite_evidence.modified_pages_delete_gate(counts, file_control_supported=supported)
    assert gate["status"] == expected and gate["private_import_allowed"] is False


@pytest.mark.parametrize("rows", [True, 0, 8193])
def test_modified_workload_rejects_unbounded_rows_before_creating_root(tmp_path, rows):
    root = tmp_path / "new"
    with pytest.raises(ProbeProblem):
        run_modified_pages_delete(root, rows=rows)
    assert not root.exists()


def test_modified_workload_preserves_existing_root_and_evidence(tmp_path):
    root = tmp_path / "existing"
    root.mkdir()
    sentinel = root / "synthetic-evidence"
    sentinel.write_bytes(b"preserved")
    with pytest.raises(ProbeProblem):
        run_modified_pages_delete(root, rows=32)
    assert sentinel.read_bytes() == b"preserved"
