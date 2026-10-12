"""Synthetic acceptance boundary repros; no actual owner evidence or provider access."""

import hashlib
import json
import subprocess
import traceback
from dataclasses import replace
from pathlib import Path

import pytest

from nexus import machine_check
from nexus.adapter_contracts import (
    AdapterIdentity,
    HistoryCoverage,
    ParsedHistory,
    dry_run_history,
    real_format_gates,
)
from nexus.connector_contracts import (
    PlanningProblem,
    ReviewCheckpoint,
    SourceScope,
    TaskIntent,
    intent_fingerprint,
    plan_task,
    planning_summary,
    simulate_transition,
)
from nexus.importers import Conversation, Message

MARKER = "PRIVATE-SYNTHETIC-FORENSIC"
REVIEW = "private-synthetic-review"
NOW = "2026-10-12T00:00:00+00:00"


def invented_history(provider="openai", product="consumer_chatgpt"):
    identity = AdapterIdentity(provider, product, "invented-forensic-1", REVIEW)
    content = MARKER + " 日本語 body"
    message = Message(MARKER + "-message", "user", content, None,
                      hashlib.sha256(content.encode("utf-8")).hexdigest())
    conversation = Conversation(MARKER + "-conversation", MARKER + " title", [message])
    return ParsedHistory(identity, (conversation,), HistoryCoverage())


def intent_and_review():
    scope = SourceScope("openai", "codex_local", "source-forensic", "account-forensic",
                        "project-forensic")
    intent = TaskIntent(scope, "task-forensic", "dedupe-forensic", "dispatch_new", MARKER)
    review = ReviewCheckpoint(scope, intent.task_ref, REVIEW, intent_fingerprint(intent),
                              "2026-10-11T00:00:00+00:00", "2026-10-13T00:00:00+00:00")
    return intent, review


def stub_probe_start(monkeypatch):
    def interrupted(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(machine_check, "powershell", lambda *_a: {
        "allowlist_only": True, "owner_allowed": True, "protected_root": True,
    })
    monkeypatch.setattr(machine_check, "_start", interrupted)


@pytest.mark.parametrize("attestation", [1, "false", None, []],
                         ids=["integer", "string", "null", "collection"])
def test_offline_attestation_requires_an_exact_boolean_before_probe_side_effects(
    tmp_path, monkeypatch, attestation,
):
    # This fixture declares a context; it is not a Windows-machine measurement.
    report = machine_check.new_report("a" * 40, True, "owner_windows")
    before = json.dumps(report, sort_keys=True)
    stub_probe_start(monkeypatch)
    with pytest.raises(ValueError, match="attestation") as failure:
        machine_check.run_probe(Path(__file__).resolve().parents[1], tmp_path, report, attestation)
    assert MARKER not in str(failure.value)
    assert json.dumps(report, sort_keys=True) == before
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("attestation", [False, True])
def test_boolean_attestation_survives_validation_but_interrupted_probe_is_not_a_pass(
    tmp_path, monkeypatch, attestation,
):
    report = machine_check.new_report("a" * 40, True, "owner_windows")
    stub_probe_start(monkeypatch)
    machine_check.run_probe(Path(__file__).resolve().parents[1], tmp_path, report, attestation)
    assert report["gates"]["cold_start"] == {"status": "FAIL", "reason": "interrupted"}
    assert report["gates"]["offline_cold_start"] == {
        "status": "NOT RUN", "reason": "operator_required",
    }
    assert report["official_v1"] == "BLOCKED"
    assert all(report["gates"][gate]["status"] == "NOT RUN"
               for gate in machine_check.GATES[9:])


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_cancelled_plan_cannot_claim_prior_attempts_without_a_review_snapshot(attempts):
    intent, _review = intent_and_review()
    with pytest.raises(PlanningProblem) as failure:
        replace(plan_task(intent), stage="simulation_cancelled", attempts=attempts)
    assert MARKER not in str(failure.value)


@pytest.mark.parametrize("cancel_at", ["awaiting_review", "reviewed", "simulation_running"])
def test_legal_cancellation_preserves_the_review_and_attempt_evidence(cancel_at):
    intent, review = intent_and_review()
    state = plan_task(intent)
    if cancel_at != "awaiting_review":
        state = simulate_transition(intent, state, "review", now=NOW, checkpoint=review)
    if cancel_at == "simulation_running":
        state = simulate_transition(intent, state, "start", now=NOW, checkpoint=review)
    cancelled = simulate_transition(intent, state, "cancel", now=NOW)
    assert cancelled.attempts == state.attempts
    assert cancelled.review_ref == state.review_ref
    assert cancelled.review_sha256 == state.review_sha256
    summary = planning_summary(cancelled)
    assert summary["stage"] == "simulation_cancelled"
    assert summary["connected"] is summary["execution_enabled"] is False
    assert summary["provider_calls"] == summary["cost_microunits"] == 0
    with pytest.raises(PlanningProblem):
        simulate_transition(intent, cancelled, "start", now=NOW, checkpoint=review)


def test_normalized_history_repr_does_not_expose_source_text_ids_or_hashes():
    history = invented_history()
    rendered = repr(history)
    assert MARKER not in rendered
    assert REVIEW not in rendered
    assert history.conversations[0].messages[0].content_sha256 not in rendered
    assert "untrusted_source_data" in rendered


def test_adapter_identity_repr_hides_private_review_reference():
    identity = invented_history().identity
    assert REVIEW not in repr(identity)
    assert identity.provider in repr(identity) and identity.product in repr(identity)
    assert identity.schema_evidence_id == REVIEW


@pytest.mark.parametrize("provider,product", [("openai", "consumer_chatgpt"),
                                            ("anthropic", "consumer_claude")])
def test_repr_redaction_preserves_dry_run_namespace_validation_and_disabled_real_gate(
    provider, product,
):
    history = invented_history(provider, product)

    class ReviewedSyntheticParser:
        identity = history.identity

        def parse(self, _payload):
            return history

    summary = dry_run_history(ReviewedSyntheticParser(), b"synthetic-only", history.identity)
    assert summary["provider"] == provider and summary["product"] == product
    assert summary["conversations"] == summary["messages"] == 1
    assert summary["stored_records"] == 0 and summary["real_format_verified"] is False
    assert MARKER not in json.dumps(summary) and REVIEW not in json.dumps(summary)
    assert history.conversations[0].messages[0].content.startswith(MARKER)
    assert all(gate["state"] == "BLOCKED" and gate["enabled"] is False
               for gate in real_format_gates())


@pytest.mark.parametrize("fault", ["timeout", "subprocess", "missing_executable"])
def test_inspector_transport_errors_have_fixed_diagnostics_without_command_or_output(
    monkeypatch, fault,
):
    if fault == "timeout":
        error = subprocess.TimeoutExpired([MARKER], 0.1, output=MARKER.encode())
    elif fault == "subprocess":
        error = subprocess.CalledProcessError(1, [MARKER], stderr=MARKER.encode())
    else:
        error = FileNotFoundError(2, "synthetic inspector unavailable", MARKER)

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(machine_check.shutil, "which", lambda *_a: "synthetic-inspector")
    monkeypatch.setattr(machine_check.subprocess, "run", fail)
    with pytest.raises(ValueError, match="inspection") as failure:
        machine_check.powershell(Path(__file__).resolve().parents[1], "Inspect-TestOperator.ps1")
    assert str(failure.value) == "Windows inspection failed"
    assert MARKER not in "".join(traceback.format_exception(failure.value))
    assert failure.value.__suppress_context__ is True


def test_inspector_keyboard_interrupt_remains_an_interrupt_for_the_probe(monkeypatch):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(machine_check.shutil, "which", lambda *_a: "synthetic-inspector")
    monkeypatch.setattr(machine_check.subprocess, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        machine_check.powershell(Path(__file__).resolve().parents[1], "Inspect-TestOperator.ps1")
