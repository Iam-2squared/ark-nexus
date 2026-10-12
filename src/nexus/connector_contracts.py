"""Pure, bounded connector planning contracts; never authorization or execution.

These V2--V4 research types have no network, filesystem, subprocess or credential
access. Even a valid or fabricated checkpoint permits simulation only. V1's
DisabledConnector remains the sole runtime connector implementation.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

from nexus.importers import ImportProblem, source_timestamp

PLANNING_CONTRACT_VERSION = "connector-planning-contract-1"
NEXUS_REPOSITORY = "Iam-2squared/ark-nexus"
PRODUCT_NAMESPACES = frozenset({
    ("openai", "consumer_chatgpt"), ("anthropic", "consumer_claude"),
    ("openai", "chatgpt_work"), ("openai", "codex_local"),
    ("openai", "codex_cloud"), ("anthropic", "claude_code"),
})
_PLANNED_TASK_OPERATIONS = frozenset({
    ("codex_local", "dispatch_new"), ("codex_local", "resume_existing"),
    ("codex_cloud", "dispatch_new"),
    ("claude_code", "dispatch_new"), ("claude_code", "resume_existing"),
})
MAX_PAGE_EVENTS = 1000
MAX_PLAN_LEDGER = 1000
MAX_SIMULATION_ATTEMPTS = 3


class PlanningProblem(ValueError):
    """Fixed diagnostics contain no source IDs, objective, cursor or private paths."""


def _reject() -> None:
    raise PlanningProblem("Connector planning contract refused; private details omitted") from None


def _token(value: object) -> None:
    if type(value) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
        _reject()


def _text(value: object, maximum: int) -> None:
    if type(value) is not str or not value or len(value) > maximum or "\x00" in value:
        _reject()
    try:
        value.encode("utf-8")
    except UnicodeError:
        _reject()


def _source_time(value: object) -> None:
    if type(value) is not str:
        _reject()
    try:
        source_timestamp(value)
    except ImportProblem:
        _reject()


def _time(value: object) -> datetime:
    # These are Nexus observation/review clocks, not a vendor's raw occurrence
    # representation. Reject precision datetime would silently truncate before
    # comparing freshness or a review lease. No rounding or coercion is allowed.
    _source_time(value)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value):
        _reject()
    return datetime.fromisoformat(value)


def _digest(value: object) -> None:
    if type(value) is not str or not re.fullmatch(r"[a-f0-9]{64}", value):
        _reject()


@dataclass(frozen=True)
class SourceScope:
    provider: str
    product: str
    source_ref: str = field(repr=False)
    account_ref: str = field(repr=False)
    project_ref: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.provider) is not str or type(self.product) is not str
                or (self.provider, self.product) not in PRODUCT_NAMESPACES):
            _reject()
        for value in (self.source_ref, self.account_ref, self.project_ref):
            _token(value)


def _scope(value: object) -> None:
    if type(value) is not SourceScope:
        _reject()
    value.__post_init__()


@dataclass(frozen=True)
class SourceObservation:
    """Metadata only. Source text is never a planning action or a tool instruction."""

    scope: SourceScope
    external_id: str = field(repr=False)
    occurred_at: str | None = field(repr=False)
    observed_at: str = field(repr=False)
    kind: Literal["history_record", "status_snapshot", "coverage_gap"]
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"

    def __post_init__(self) -> None:
        _scope(self.scope)
        _text(self.external_id, 1000)
        if self.occurred_at is not None:
            _source_time(self.occurred_at)
        _time(self.observed_at)
        if (type(self.kind) is not str
                or self.kind not in {"history_record", "status_snapshot", "coverage_gap"}
                or type(self.trust) is not str or self.trust != "untrusted_source_data"):
            _reject()


@dataclass(frozen=True)
class HistoryCursor:
    scope: SourceScope
    parser_version: str
    opaque_token: str = field(repr=False)
    observed_at: str = field(repr=False)

    def __post_init__(self) -> None:
        _scope(self.scope)
        _token(self.parser_version)
        _text(self.opaque_token, 4096)
        _time(self.observed_at)


@dataclass(frozen=True)
class HistoryBatch:
    scope: SourceScope
    parser_version: str
    events: tuple[SourceObservation, ...] = field(repr=False)
    next_cursor: HistoryCursor | None = field(default=None, repr=False)
    complete: bool = False

    def __post_init__(self) -> None:
        _scope(self.scope)
        _token(self.parser_version)
        if (type(self.complete) is not bool or type(self.events) is not tuple
                or len(self.events) > MAX_PAGE_EVENTS):
            _reject()
        identities = set()
        for event in self.events:
            if type(event) is not SourceObservation:
                _reject()
            event.__post_init__()
            if event.scope != self.scope or event.external_id in identities:
                _reject()
            identities.add(event.external_id)
        if self.next_cursor is not None:
            if type(self.next_cursor) is not HistoryCursor:
                _reject()
            self.next_cursor.__post_init__()
            if (self.complete or self.next_cursor.scope != self.scope
                    or self.next_cursor.parser_version != self.parser_version):
                _reject()
            if any(_time(event.observed_at) > _time(self.next_cursor.observed_at)
                   for event in self.events):
                _reject()
        if self.complete and any(event.kind == "coverage_gap" for event in self.events):
            _reject()


def review_history_batch(batch: HistoryBatch, expected_scope: SourceScope,
                         expected_parser_version: str,
                         previous_cursor: HistoryCursor | None = None) -> dict:
    """Validate a single scoped page without persisting data or promoting coverage.

    A provider may legitimately return an incomplete final snapshot with no
    cursor. This remains complete=False and cannot imply missing-record deletion.
    Cross-page deduplication still needs a future transaction-backed importer.
    """
    _scope(expected_scope)
    _token(expected_parser_version)
    if type(batch) is not HistoryBatch:
        _reject()
    batch.__post_init__()
    if batch.scope != expected_scope or batch.parser_version != expected_parser_version:
        _reject()
    if previous_cursor is not None:
        if type(previous_cursor) is not HistoryCursor:
            _reject()
        previous_cursor.__post_init__()
        if (previous_cursor.scope != expected_scope
                or previous_cursor.parser_version != expected_parser_version):
            _reject()
        previous_time = _time(previous_cursor.observed_at)
        if any(_time(event.observed_at) < previous_time for event in batch.events):
            _reject()
        if batch.next_cursor is not None and (
            batch.next_cursor.opaque_token == previous_cursor.opaque_token
            or _time(batch.next_cursor.observed_at) < previous_time
        ):
            _reject()
    return {"mode": "contract_review", "contract_version": PLANNING_CONTRACT_VERSION,
            "provider": expected_scope.provider, "product": expected_scope.product,
            "events": len(batch.events), "complete": batch.complete,
            "has_next_cursor": batch.next_cursor is not None,
            "connected": False, "execution_enabled": False, "stored_records": 0}


@dataclass(frozen=True)
class TaskIntent:
    scope: SourceScope
    task_ref: str = field(repr=False)
    idempotency_ref: str = field(repr=False)
    operation: Literal["dispatch_new", "resume_existing"]
    objective: str = field(repr=False)
    allowed_repository: str = NEXUS_REPOSITORY
    session_ref: str | None = field(default=None, repr=False)
    max_attempts: int = 1
    max_cost_microunits: int = 0

    def __post_init__(self) -> None:
        _scope(self.scope)
        _token(self.task_ref)
        _token(self.idempotency_ref)
        _text(self.objective, 4000)
        if (type(self.operation) is not str
                or self.operation not in {"dispatch_new", "resume_existing"}
                or (self.scope.product, self.operation) not in _PLANNED_TASK_OPERATIONS
                or type(self.allowed_repository) is not str
                or self.allowed_repository != NEXUS_REPOSITORY
                or type(self.max_attempts) is not int
                or not 1 <= self.max_attempts <= MAX_SIMULATION_ATTEMPTS
                or type(self.max_cost_microunits) is not int or self.max_cost_microunits != 0):
            _reject()
        if self.operation == "resume_existing":
            _token(self.session_ref)
        elif self.session_ref is not None:
            _reject()


def intent_fingerprint(intent: TaskIntent) -> str:
    if type(intent) is not TaskIntent:
        _reject()
    intent.__post_init__()
    values = (PLANNING_CONTRACT_VERSION, intent.scope.provider, intent.scope.product,
              intent.scope.source_ref, intent.scope.account_ref, intent.scope.project_ref,
              intent.task_ref, intent.idempotency_ref, intent.operation, intent.objective,
              intent.allowed_repository, intent.session_ref, intent.max_attempts,
              intent.max_cost_microunits)
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewCheckpoint:
    """Unverified review metadata, not a credential or a provider execution grant."""

    scope: SourceScope
    task_ref: str = field(repr=False)
    review_ref: str = field(repr=False)
    intent_sha256: str = field(repr=False)
    approved_at: str = field(repr=False)
    expires_at: str = field(repr=False)

    def __post_init__(self) -> None:
        _scope(self.scope)
        _token(self.task_ref)
        _token(self.review_ref)
        _digest(self.intent_sha256)
        if _time(self.expires_at) <= _time(self.approved_at):
            _reject()


def _checkpoint_fingerprint(checkpoint: ReviewCheckpoint) -> str:
    checkpoint.__post_init__()
    values = (PLANNING_CONTRACT_VERSION, checkpoint.scope.provider, checkpoint.scope.product,
              checkpoint.scope.source_ref, checkpoint.scope.account_ref, checkpoint.scope.project_ref,
              checkpoint.task_ref, checkpoint.review_ref, checkpoint.intent_sha256,
              checkpoint.approved_at, checkpoint.expires_at)
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


PlanStage = Literal["awaiting_review", "reviewed", "simulation_running", "simulation_paused",
                    "simulation_complete", "simulation_failed", "simulation_cancelled"]
_STAGES = frozenset({"awaiting_review", "reviewed", "simulation_running", "simulation_paused",
                     "simulation_complete", "simulation_failed", "simulation_cancelled"})


@dataclass(frozen=True)
class TaskPlanState:
    scope: SourceScope
    task_ref: str = field(repr=False)
    idempotency_ref: str = field(repr=False)
    intent_sha256: str = field(repr=False)
    stage: PlanStage = "awaiting_review"
    attempts: int = 0
    review_ref: str | None = field(default=None, repr=False)
    review_sha256: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _scope(self.scope)
        _token(self.task_ref)
        _token(self.idempotency_ref)
        _digest(self.intent_sha256)
        if (type(self.stage) is not str or self.stage not in _STAGES
                or type(self.attempts) is not int
                or not 0 <= self.attempts <= MAX_SIMULATION_ATTEMPTS):
            _reject()
        if self.review_ref is not None:
            _token(self.review_ref)
        if self.review_sha256 is not None:
            _digest(self.review_sha256)
        if (self.review_ref is None) != (self.review_sha256 is None):
            _reject()
        if self.stage in {"awaiting_review", "reviewed"} and self.attempts != 0:
            _reject()
        if self.stage == "awaiting_review" and self.review_ref is not None:
            _reject()
        if self.stage != "simulation_cancelled" and self.stage != "awaiting_review":
            if self.review_ref is None:
                _reject()
            if self.stage != "reviewed" and self.attempts == 0:
                _reject()


def plan_task(intent: TaskIntent, existing: tuple[TaskPlanState, ...] = ()) -> TaskPlanState:
    fingerprint = intent_fingerprint(intent)
    if type(existing) is not tuple or len(existing) >= MAX_PLAN_LEDGER:
        _reject()
    for state in existing:
        if type(state) is not TaskPlanState:
            _reject()
        state.__post_init__()
        if state.task_ref == intent.task_ref or state.idempotency_ref == intent.idempotency_ref:
            _reject()
    return TaskPlanState(intent.scope, intent.task_ref, intent.idempotency_ref, fingerprint)


def _checkpoint(intent: TaskIntent, state: TaskPlanState, checkpoint: ReviewCheckpoint | None,
                now: str) -> ReviewCheckpoint:
    current = _time(now)
    if type(checkpoint) is not ReviewCheckpoint:
        _reject()
    checkpoint.__post_init__()
    if (checkpoint.scope != intent.scope or checkpoint.task_ref != intent.task_ref
            or checkpoint.intent_sha256 != state.intent_sha256
            or not _time(checkpoint.approved_at) <= current < _time(checkpoint.expires_at)
            or (state.review_ref is not None and checkpoint.review_ref != state.review_ref)
            or (state.review_sha256 is not None
                and _checkpoint_fingerprint(checkpoint) != state.review_sha256)):
        _reject()
    return checkpoint


def simulate_transition(intent: TaskIntent, state: TaskPlanState, action: str, *, now: str,
                        checkpoint: ReviewCheckpoint | None = None) -> TaskPlanState:
    """Model a transition without invoking Connector or treating data as an instruction."""
    fingerprint = intent_fingerprint(intent)
    if type(state) is not TaskPlanState or type(action) is not str:
        _reject()
    state.__post_init__()
    _time(now)
    if (state.scope != intent.scope or state.task_ref != intent.task_ref
            or state.idempotency_ref != intent.idempotency_ref
            or state.intent_sha256 != fingerprint or state.attempts > intent.max_attempts):
        _reject()
    transitions = {
        ("awaiting_review", "review"): "reviewed",
        ("reviewed", "start"): "simulation_running",
        ("simulation_running", "pause"): "simulation_paused",
        ("simulation_paused", "resume"): "simulation_running",
        ("simulation_running", "succeed"): "simulation_complete",
        ("simulation_running", "fail"): "simulation_failed",
        ("simulation_failed", "retry"): "simulation_running",
    }
    if state.stage in {"simulation_complete", "simulation_cancelled"}:
        _reject()
    if action == "cancel":
        return replace(state, stage="simulation_cancelled")
    next_stage = transitions.get((state.stage, action))
    if next_stage is None:
        _reject()
    if action in {"review", "start", "resume", "retry"}:
        checkpoint = _checkpoint(intent, state, checkpoint, now)
    attempts = state.attempts + int(action in {"start", "retry"})
    if attempts > intent.max_attempts:
        _reject()
    return replace(state, stage=next_stage, attempts=attempts,
                   review_ref=checkpoint.review_ref if action == "review" else state.review_ref,
                   review_sha256=_checkpoint_fingerprint(checkpoint) if action == "review"
                   else state.review_sha256)


def planning_summary(state: TaskPlanState) -> dict:
    if type(state) is not TaskPlanState:
        _reject()
    state.__post_init__()
    return {"mode": "simulation_only", "contract_version": PLANNING_CONTRACT_VERSION,
            "provider": state.scope.provider, "product": state.scope.product,
            "stage": state.stage, "attempts": state.attempts,
            "connected": False, "execution_enabled": False,
            "provider_calls": 0, "cost_microunits": 0}
