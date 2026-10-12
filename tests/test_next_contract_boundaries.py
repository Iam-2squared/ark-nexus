"""Local control clocks and unchanged review leases; synthetic contracts only."""

import hashlib
import json
from dataclasses import replace

import pytest

from nexus.adapter_contracts import (
    AdapterIdentity,
    HistoryCoverage,
    ParsedHistory,
    dry_run_history,
    real_format_gates,
)
from nexus.connector_contracts import (
    HistoryBatch,
    HistoryCursor,
    PlanningProblem,
    ReviewCheckpoint,
    SourceObservation,
    SourceScope,
    TaskIntent,
    intent_fingerprint,
    plan_task,
    planning_summary,
    review_history_batch,
    simulate_transition,
)
from nexus.connectors import DisabledConnector, connection_catalog
from nexus.importers import Conversation, Message

NOW = "2026-01-01T12:00:00+00:00"
BEFORE = "2026-01-01T11:00:00+00:00"
AFTER = "2026-01-01T13:00:00+00:00"
LATER = "2026-01-01T14:00:00+00:00"
SCOPE = SourceScope("openai", "codex_local", "source-next", "account-next", "project-next")


def request_and_checkpoint():
    request = TaskIntent(SCOPE, "task-next", "idempotency-next", "dispatch_new",
                         "PRIVATE-SYNTHETIC objective", max_attempts=2)
    checkpoint = ReviewCheckpoint(SCOPE, request.task_ref, "review-next",
                                  intent_fingerprint(request), BEFORE, AFTER)
    return request, checkpoint


def ready_for(action):
    request, checkpoint = request_and_checkpoint()
    state = simulate_transition(request, plan_task(request), "review", now=NOW,
                                checkpoint=checkpoint)
    if action != "start":
        state = simulate_transition(request, state, "start", now=NOW, checkpoint=checkpoint)
        state = simulate_transition(request, state, "pause" if action == "resume" else "fail",
                                    now=NOW)
    return request, checkpoint, state


@pytest.mark.parametrize("action", ["start", "resume", "retry"])
@pytest.mark.parametrize("field,value", [("approved_at", "2026-01-01T10:00:00+00:00"),
                                         ("expires_at", LATER)])
def test_same_review_reference_cannot_replace_the_reviewed_lease(action, field, value):
    request, checkpoint, state = ready_for(action)
    changed = replace(checkpoint, **{field: value})
    with pytest.raises(PlanningProblem) as failure:
        simulate_transition(request, state, action, now=NOW, checkpoint=changed)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)
    assert state.stage != "simulation_complete"


@pytest.mark.parametrize("action", ["start", "resume", "retry"])
def test_in_place_expiry_extension_cannot_revive_an_expired_review(action):
    request, checkpoint, state = ready_for(action)
    # Frozen metadata is revalidated; it is not an authority or a Python sandbox.
    object.__setattr__(checkpoint, "expires_at", LATER)
    with pytest.raises(PlanningProblem):
        simulate_transition(request, state, action, now=AFTER, checkpoint=checkpoint)


@pytest.mark.parametrize("action", ["start", "resume", "retry"])
def test_an_unchanged_checkpoint_copy_keeps_the_reviewed_simulation_lease(action):
    request, checkpoint, state = ready_for(action)
    updated = simulate_transition(request, state, action, now=NOW, checkpoint=replace(checkpoint))
    summary = planning_summary(updated)
    assert summary["stage"] == "simulation_running"
    assert summary["connected"] is summary["execution_enabled"] is False
    assert summary["provider_calls"] == summary["cost_microunits"] == 0
    assert "PRIVATE-SYNTHETIC" not in json.dumps(summary)


@pytest.mark.parametrize("clock", ["observation", "cursor", "approval", "expiry", "now"])
def test_control_clocks_refuse_precision_datetime_would_silently_truncate(clock):
    precise = "2026-01-01T12:00:00.1234567+00:00"
    with pytest.raises(PlanningProblem) as failure:
        if clock == "observation":
            SourceObservation(SCOPE, "event-next", None, precise, "history_record")
        elif clock == "cursor":
            HistoryCursor(SCOPE, "synthetic-next-1", "PRIVATE-SYNTHETIC-CURSOR", precise)
        else:
            request, checkpoint = request_and_checkpoint()
            if clock == "approval":
                checkpoint = replace(checkpoint, approved_at=precise)
                now = "2026-01-01T12:00:00.1234561+00:00"
            elif clock == "expiry":
                checkpoint = replace(checkpoint, expires_at=precise)
                now = NOW
            else:
                now = precise
            simulate_transition(request, plan_task(request), "review", now=now,
                                checkpoint=checkpoint)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)


@pytest.mark.parametrize("clock", [
    "2026-01-01T12:00:00.123456+00:00",
    "2026-01-01T21:00:00.123456+09:00",
    "2026-01-01T12:00:00Z",
    "2026-01-01T12:00:00.1+00:00",
])
def test_explicit_local_clock_precision_and_timezone_remain_lossless(clock):
    observation = SourceObservation(SCOPE, "event-next", None, clock, "history_record")
    cursor = HistoryCursor(SCOPE, "synthetic-next-1", "PRIVATE-SYNTHETIC-CURSOR", clock)
    batch = HistoryBatch(SCOPE, "synthetic-next-1", (observation,), cursor)
    summary = review_history_batch(batch, SCOPE, "synthetic-next-1")
    assert summary["events"] == 1
    assert observation.observed_at == cursor.observed_at == clock
    assert "PRIVATE-SYNTHETIC" not in json.dumps(summary)


@pytest.mark.parametrize("timestamp", [
    "2025-12-31T23:59:59.1234567+09:00",
    "2025-12-31T23:59:59.123456789+09:00",
])
def test_raw_occurrence_precision_is_preserved_without_reusing_it_as_a_control_clock(timestamp):
    observation = SourceObservation(SCOPE, "event-next", timestamp, NOW, "history_record")
    identity = AdapterIdentity("openai", "consumer_chatgpt", "synthetic-next-1", "review-next")
    body = "日本語 synthetic"
    message = Message("message-next", "user", body, timestamp,
                      hashlib.sha256(body.encode()).hexdigest())
    history = ParsedHistory(identity, (Conversation("conversation-next", "synthetic", [message]),),
                            HistoryCoverage())

    class ReviewedSyntheticParser:
        def __init__(self):
            self.identity = identity

        def parse(self, _payload):
            return history

    summary = dry_run_history(ReviewedSyntheticParser(), b"synthetic-only", identity)
    assert observation.occurred_at == history.conversations[0].messages[0].occurred_at == timestamp
    assert summary["stored_records"] == 0 and summary["real_format_verified"] is False


def test_valid_review_lease_still_cannot_enable_any_runtime_connector_or_real_parser():
    request, checkpoint, state = ready_for("start")
    running = simulate_transition(request, state, "start", now=NOW, checkpoint=checkpoint)
    summary = planning_summary(running)
    assert summary["provider_calls"] == summary["cost_microunits"] == 0
    assert all(row["connection_state"] == "not_connected" and not row["implemented"]
               and not row["execution_enabled"] for row in connection_catalog())
    assert len(connection_catalog()) == 6
    assert len(real_format_gates()) == 2
    assert all(row["state"] == "BLOCKED" and not row["enabled"] for row in real_format_gates())
    with pytest.raises(PermissionError):
        DisabledConnector().resume_existing(request)
