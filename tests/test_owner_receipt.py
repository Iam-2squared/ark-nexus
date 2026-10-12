"""Synthetic receipt validation. No owner evidence or Windows access is fabricated."""

import json
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from nexus import machine_check
from nexus.owner_receipt import (
    MAX_RECEIPT_BYTES,
    OwnerReceiptRejected,
    validate_owner_receipt,
)

HEAD = "a" * 40
MARKER = "PRIVATE-SYNTHETIC-RECEIPT"


def report_bytes(report):
    return json.dumps(report, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def owner_report():
    # A declared report fixture, not evidence from a Windows owner machine.
    report = machine_check.new_report(HEAD, True, "owner_windows")
    report["checked_at"] = "2026-10-12T00:00:00.123456+00:00"
    for gate in machine_check.GATES[:8]:
        machine_check.record(report, gate, "PASS")
    for gate in machine_check.GATES[8:12]:
        machine_check.record(report, gate, "NOT RUN", "operator_required")
    for gate in machine_check.GATES[12:]:
        machine_check.record(report, gate, "NOT RUN", "approved_sample_required")
    return report


def assert_rejected(payload, code=None, expected_head=HEAD):
    with pytest.raises(OwnerReceiptRejected) as result:
        validate_owner_receipt(payload, expected_head=expected_head)
    rendered = "".join(traceback.format_exception(result.value))
    assert MARKER not in rendered
    if code:
        assert result.value.code == code


@pytest.mark.parametrize("script,payload", [
    ("Inspect-TestDirectory.ps1",
     b'{"allowlist_only":false,"owner_allowed":true,"protected_root":true,'
     b'"allowlist_only":true}'),
    ("Inspect-TestListener.ps1",
     b'{"owned_loopback_only":false,"owned_loopback_only":true}'),
    ("Inspect-TestOperator.ps1", b'{"standard_user":false,"standard_user":true}'),
], ids=["acl", "listener", "operator"])
def test_inspection_duplicate_fields_cannot_replace_a_failed_boundary(monkeypatch, script, payload):
    repo = Path(__file__).resolve().parents[1]

    class Result:
        returncode = 0
        stdout = payload

    monkeypatch.setattr(machine_check.shutil, "which", lambda *_a: "synthetic-inspector")
    monkeypatch.setattr(machine_check.subprocess, "run", lambda *_a, **_k: Result())
    with pytest.raises(ValueError, match="inspection"):
        machine_check.powershell(repo, script)


def test_owner_receipt_accepts_only_synthetic_classifications_and_has_no_io(monkeypatch):
    payload = report_bytes(owner_report())

    def unexpected(*_args, **_kwargs):
        pytest.fail("Pure receipt validation must not read files, run a process or contact a server")

    monkeypatch.setattr(Path, "open", unexpected)
    monkeypatch.setattr(machine_check.subprocess, "run", unexpected)
    monkeypatch.setattr(machine_check, "run_probe", unexpected)
    monkeypatch.setattr(machine_check, "request", unexpected)
    receipt = validate_owner_receipt(payload, expected_head=HEAD)
    summary = receipt.summary()
    assert summary["automatic_gates"] == {"PASS": 8, "FAIL": 0, "NOT RUN": 0, "total": 8}
    assert summary["official_v1"] == "BLOCKED"
    assert summary["origin"] == "owner_declared_not_authenticated"
    assert summary["offline_cold_start"] == "NOT RUN"
    assert summary["owner_manual_gates"] == summary["real_format_gates"] == "NOT RUN"
    assert json.loads(payload) == owner_report(), "Receipt input must not be rewritten"
    with pytest.raises(FrozenInstanceError):
        receipt.head = "b" * 40


def test_operator_attested_offline_receipt_remains_blocked_and_separate_from_manual_gates():
    report = owner_report()
    machine_check.record(report, "offline_cold_start", "PASS", "operator_attested")
    summary = validate_owner_receipt(report_bytes(report), expected_head=HEAD).summary()
    assert summary["offline_cold_start"] == "PASS"
    assert summary["automatic_gates"]["PASS"] == 8
    assert summary["official_v1"] == "BLOCKED"
    assert summary["owner_manual_gates"] == "NOT RUN"


@pytest.mark.parametrize("reason", ["check_failed", "interrupted"])
def test_failed_probe_and_later_unattempted_gates_are_preserved(reason):
    report = owner_report()
    for gate in machine_check.GATES[1:8]:
        machine_check.record(report, gate, "NOT RUN", "not_attempted")
    machine_check.record(report, "cold_start", "FAIL", reason)
    receipt = validate_owner_receipt(report_bytes(report), expected_head=HEAD)
    assert receipt.summary()["automatic_gates"] == {"PASS": 0, "FAIL": 1, "NOT RUN": 7, "total": 8}
    assert receipt.summary()["official_v1"] == "BLOCKED"


@pytest.mark.parametrize("context", ["github_runner", "test_harness"])
def test_runner_or_test_harness_cannot_supply_owner_evidence(context):
    report = owner_report()
    report["context"] = context
    assert_rejected(report_bytes(report), "owner_context_required")


def test_exact_source_head_binding_refuses_different_source_or_pr_merge_sha():
    assert_rejected(report_bytes(owner_report()), "head_mismatch", expected_head="b" * 40)


@pytest.mark.parametrize("head", [MARKER, "A" * 40, "a" * 39, None, True])
def test_expected_revision_binding_is_strict_and_redacted(head):
    assert_rejected(report_bytes(owner_report()), "invalid_binding", expected_head=head)


@pytest.mark.parametrize("clean", [False, "true", None])
def test_dirty_or_coerced_owner_working_tree_is_rejected(clean):
    report = owner_report()
    report["working_tree_clean"] = clean
    assert_rejected(report_bytes(report), "clean_checkout_required")


@pytest.mark.parametrize("payload", [
    b"", b"\xff", b'{"private":"PRIVATE-SYNTHETIC-RECEIPT"', b'{}\x00', b"[]", b"true",
    b'{"schema":NaN}', b'{"schema":1.0}', b'{"schema":123}',
    b'"PRIVATE-SYNTHETIC-RECEIPT"',
], ids=["empty", "utf8", "malformed", "nul", "array", "boolean", "nan", "float", "integer",
        "scalar-secret"])
def test_malformed_or_non_schema_json_is_rejected_without_raw_diagnostics(payload):
    assert_rejected(payload)


def test_receipt_size_cap_is_checked_before_decoder(monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail("Oversized receipts must not reach the JSON decoder")

    monkeypatch.setattr(json, "loads", unexpected)
    assert_rejected(b" " * (MAX_RECEIPT_BYTES + 1), "payload_too_large")


@pytest.mark.parametrize("payload", [None, "PRIVATE-SYNTHETIC-RECEIPT", bytearray(b"{}")])
def test_receipt_accepts_exact_bytes_only(payload):
    assert_rejected(payload, "invalid_json")


@pytest.mark.parametrize("old,new", [
    (b'"head":', b'"head":"PRIVATE-SYNTHETIC-RECEIPT","head":'),
    (b'"cold_start":', b'"cold_start":{"status":"FAIL","reason":"check_failed"},"cold_start":'),
    (b'"status":"PASS"', b'"status":"FAIL","status":"PASS"'),
    (b'"reason":"verified"', b'"reason":"PRIVATE-SYNTHETIC-RECEIPT","reason":"verified"'),
], ids=["head", "gate", "status", "reason"])
def test_duplicate_fields_at_every_schema_level_are_rejected(old, new):
    payload = report_bytes(owner_report()).replace(old, new, 1)
    assert_rejected(payload, "invalid_json")


@pytest.mark.parametrize("field,value", [
    ("schema", MARKER), ("repository", "Iam-2squared/ark-ai"), ("data_kind", "private"),
    ("official_v1", "PASS"), ("python", "3.14"), ("python", None),
    ("checked_at", "2026-10-12T00:00:00"), ("checked_at", "2026-10-12T00:00:00+01:00"),
    ("checked_at", "2026-02-30T00:00:00+00:00"), ("checked_at", MARKER),
], ids=["schema", "repository", "data-kind", "official", "python", "python-null", "naive-time",
        "non-utc", "invalid-date", "private-time"])
def test_metadata_allowlist_prevents_false_claims_and_private_values(field, value):
    report = owner_report()
    report[field] = value
    assert_rejected(report_bytes(report), "invalid_metadata")


@pytest.mark.parametrize("level", ["top", "gate", "classification"])
def test_unknown_fields_cannot_smuggle_path_key_or_console_text(level):
    report = owner_report()
    if level == "top":
        report["raw_console"] = MARKER
    elif level == "gate":
        report["gates"]["private_path"] = MARKER
    else:
        report["gates"]["cold_start"]["private_key"] = MARKER
    assert_rejected(report_bytes(report))


@pytest.mark.parametrize("level", ["top", "gate", "classification"])
def test_missing_fields_do_not_turn_partial_payload_into_a_pass(level):
    report = owner_report()
    if level == "top":
        del report["repository"]
    elif level == "gate":
        del report["gates"]["cold_start"]
    else:
        del report["gates"]["cold_start"]["reason"]
    assert_rejected(report_bytes(report))


@pytest.mark.parametrize("status,reason", [
    ("PASS", "check_failed"), ("FAIL", "verified"), ("NOT RUN", "verified"),
    ("SKIP", "windows_required"), ("PASS", MARKER), (True, "verified"), ("PASS", None),
], ids=["pass-failed", "fail-verified", "not-run-verified", "windows-skip", "private-reason",
        "boolean-status", "null-reason"])
def test_automatic_gate_status_and_reason_pairs_are_strict(status, reason):
    report = owner_report()
    report["gates"]["cold_start"] = {"status": status, "reason": reason}
    assert_rejected(report_bytes(report), "invalid_classification")


@pytest.mark.parametrize("gate", machine_check.GATES[9:])
def test_manual_or_real_gate_promotion_cannot_enter_automatic_report(gate):
    report = owner_report()
    report["gates"][gate] = {"status": "PASS", "reason": "verified"}
    assert_rejected(report_bytes(report), "manual_evidence_separate")


def test_offline_attestation_requires_a_successful_cold_start():
    report = owner_report()
    machine_check.record(report, "cold_start", "FAIL", "interrupted")
    machine_check.record(report, "offline_cold_start", "PASS", "operator_attested")
    assert_rejected(report_bytes(report), "invalid_classification")


def test_fresh_unexecuted_report_cannot_be_misread_as_completed_owner_receipt():
    report = machine_check.new_report(HEAD, True, "owner_windows")
    assert_rejected(report_bytes(report))
