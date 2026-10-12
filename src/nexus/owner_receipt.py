"""Pure, bounded validation of an owner-reviewed synthetic machine report.

This does not authenticate who produced the report, read files, run probes or
convert separately reviewed manual/real-format evidence into an automatic PASS.
The machine_check report schema and its fourteen gates are unchanged.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from nexus.machine_check import GATES, REPOSITORY

MAX_RECEIPT_BYTES = 16 * 1024
REPORT_FIELDS = frozenset({
    "schema", "repository", "head", "working_tree_clean", "context", "python", "checked_at",
    "data_kind", "official_v1", "gates",
})
AUTOMATIC_GATES = GATES[:8]
MANUAL_GATES = ("owner_browser_ui", "other_os_user_denied", "private_profile_acl")
REAL_FORMAT_GATES = ("real_chatgpt_format", "real_claude_format")


class OwnerReceiptRejected(ValueError):
    """Only fixed classifications can be used by receipt callers."""

    def __init__(self, code: str):
        super().__init__("Owner receipt rejected: " + code)
        self.code = code


@dataclass(frozen=True)
class OwnerReceipt:
    head: str
    python: str
    checked_at: str
    automatic_passes: int
    automatic_failures: int
    automatic_not_run: int
    offline_cold_start: str

    def summary(self) -> dict:
        """Counts/classifications only; not a report replacement or V1 approval."""
        return {
            "repository": REPOSITORY,
            "head": self.head,
            "context": "owner_windows",
            "python": self.python,
            "checked_at": self.checked_at,
            "automatic_gates": {
                "PASS": self.automatic_passes,
                "FAIL": self.automatic_failures,
                "NOT RUN": self.automatic_not_run,
                "total": len(AUTOMATIC_GATES),
            },
            "offline_cold_start": self.offline_cold_start,
            "owner_manual_gates": "NOT RUN",
            "real_format_gates": "NOT RUN",
            "origin": "owner_declared_not_authenticated",
            "official_v1": "BLOCKED",
        }


def _json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise OwnerReceiptRejected("invalid_json")
        result[name] = value
    return result


def _json_number(_value: str) -> None:
    # The unchanged producer schema contains only strings, booleans and objects.
    raise OwnerReceiptRejected("invalid_json")


def _utc_timestamp(value: object) -> bool:
    if type(value) is not str or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00",
        value,
    ):
        return False
    try:
        return datetime.fromisoformat(value).utcoffset() == timezone.utc.utcoffset(None)
    except ValueError:
        return False


def validate_owner_receipt(payload: bytes, *, expected_head: str) -> OwnerReceipt:
    """Validate reviewed bytes against an independently selected source HEAD.

    A caller must obtain expected_head from the reviewed owner checkout/source,
    rather than copying it from this untrusted receipt or a PR merge checkout.
    Receipt metadata is self-declared; acceptance does not prove machine origin.
    No path, file, account, permission, subprocess or network operation is used.
    """
    if type(expected_head) is not str or not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise OwnerReceiptRejected("invalid_binding")
    if type(payload) is not bytes:
        raise OwnerReceiptRejected("invalid_json")
    if len(payload) > MAX_RECEIPT_BYTES:
        raise OwnerReceiptRejected("payload_too_large")
    try:
        report = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_json_object,
            parse_int=_json_number, parse_float=_json_number, parse_constant=_json_number,
        )
    except (UnicodeError, ValueError, RecursionError):
        raise OwnerReceiptRejected("invalid_json") from None
    if type(report) is not dict or set(report) != REPORT_FIELDS:
        raise OwnerReceiptRejected("invalid_fields")
    if (report["schema"] != "nexus-machine-evidence-1" or report["repository"] != REPOSITORY
            or report["data_kind"] != "synthetic" or report["official_v1"] != "BLOCKED"
            or report["python"] not in ("3.12", "3.13")
            or not _utc_timestamp(report["checked_at"])):
        raise OwnerReceiptRejected("invalid_metadata")
    if type(report["head"]) is not str or report["head"] != expected_head:
        raise OwnerReceiptRejected("head_mismatch")
    if report["context"] != "owner_windows":
        raise OwnerReceiptRejected("owner_context_required")
    if report["working_tree_clean"] is not True:
        raise OwnerReceiptRejected("clean_checkout_required")
    gates = report["gates"]
    if type(gates) is not dict or set(gates) != set(GATES):
        raise OwnerReceiptRejected("invalid_gates")
    for gate, classification in gates.items():
        if (type(classification) is not dict or set(classification) != {"status", "reason"}
                or type(classification["status"]) is not str
                or type(classification["reason"]) is not str):
            raise OwnerReceiptRejected("invalid_classification")
        pair = (classification["status"], classification["reason"])
        if gate in AUTOMATIC_GATES:
            if pair not in {("PASS", "verified"), ("FAIL", "check_failed"),
                            ("FAIL", "interrupted"), ("NOT RUN", "not_attempted")}:
                raise OwnerReceiptRejected("invalid_classification")
        elif gate == "offline_cold_start":
            if pair not in {("NOT RUN", "operator_required"), ("PASS", "operator_attested")}:
                raise OwnerReceiptRejected("invalid_classification")
            if pair[0] == "PASS" and gates["cold_start"] != {"status": "PASS", "reason": "verified"}:
                raise OwnerReceiptRejected("invalid_classification")
        elif gate in MANUAL_GATES:
            if pair != ("NOT RUN", "operator_required"):
                raise OwnerReceiptRejected("manual_evidence_separate")
        elif gate in REAL_FORMAT_GATES:
            if pair != ("NOT RUN", "approved_sample_required"):
                raise OwnerReceiptRejected("manual_evidence_separate")
    counts = {status: sum(gates[gate]["status"] == status for gate in AUTOMATIC_GATES)
              for status in ("PASS", "FAIL", "NOT RUN")}
    return OwnerReceipt(
        head=report["head"], python=report["python"], checked_at=report["checked_at"],
        automatic_passes=counts["PASS"], automatic_failures=counts["FAIL"],
        automatic_not_run=counts["NOT RUN"], offline_cold_start=gates["offline_cold_start"]["status"],
    )
