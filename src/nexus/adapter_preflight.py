"""Manifest-only private fixture review; reads no exports and enables no adapters.

Declarations are reviewer attestations, not proof of anonymization or permission.
This contract does not infer a provider schema, inspect private files, or satisfy
any real-format/Windows-owner gate.
"""

from dataclasses import dataclass, field, fields
from typing import Literal

from nexus.adapter_contracts import AdapterIdentity
from nexus.importers import ImportProblem

PREFLIGHT_VERSION = "private-fixture-manifest-1"


@dataclass(frozen=True)
class PrivateFixtureManifest:
    identity: AdapterIdentity = field(repr=False)
    owner_approved: bool = False
    anonymization_reviewed: bool = False
    dynamic_keys_reviewed: bool = False
    attachments_removed: bool = False
    raw_id_types: tuple[Literal["string", "integer"], ...] = ()
    timestamp_representation: Literal["unverified", "aware_iso", "epoch_number", "mixed"] = (
        "unverified"
    )
    timestamp_precision: Literal["unverified", "seconds", "subseconds", "mixed"] = "unverified"
    references_verified: bool = False
    source_types_preserved: bool = False
    missing_records_possible: bool = True
    branches: Literal["unverified", "absent", "preserved"] = "unverified"
    revisions: Literal["unverified", "absent", "preserved"] = "unverified"
    unknown_field_policy: Literal["unverified", "fail_closed"] = "unverified"
    parser_reviewed: bool = False
    pipeline_inert_reviewed: bool = False

    def __post_init__(self) -> None:
        if type(self.identity) is not AdapterIdentity:
            raise ImportProblem("Invalid private fixture review manifest")
        self.identity.__post_init__()
        boolean_names = {"owner_approved", "anonymization_reviewed", "dynamic_keys_reviewed",
                         "attachments_removed", "references_verified", "source_types_preserved",
                         "missing_records_possible", "parser_reviewed", "pipeline_inert_reviewed"}
        for descriptor in fields(self):
            if descriptor.name in boolean_names and type(getattr(self, descriptor.name)) is not bool:
                raise ImportProblem("Invalid private fixture review declaration")
        if (type(self.raw_id_types) is not tuple or len(self.raw_id_types) > 2
                or any(type(kind) is not str or kind not in {"string", "integer"}
                       for kind in self.raw_id_types)
                or len(set(self.raw_id_types)) != len(self.raw_id_types)):
            raise ImportProblem("Invalid private fixture source ID classification")
        classifications = {
            "timestamp_representation": {"unverified", "aware_iso", "epoch_number", "mixed"},
            "timestamp_precision": {"unverified", "seconds", "subseconds", "mixed"},
            "branches": {"unverified", "absent", "preserved"},
            "revisions": {"unverified", "absent", "preserved"},
            "unknown_field_policy": {"unverified", "fail_closed"},
        }
        for name, choices in classifications.items():
            value = getattr(self, name)
            if type(value) is not str or value not in choices:
                raise ImportProblem("Invalid private fixture structural classification")


def review_private_fixture_manifest(manifest: PrivateFixtureManifest,
                                    expected_identity: AdapterIdentity) -> dict:
    """Return fixed review codes, never paths, raw IDs, sample text or evidence refs.

    review_ready only means the declarations are complete for a future private
    review. Actual sample receipt/review, parser fixtures, activation review and
    owner-machine evidence are separate; the real gate always stays BLOCKED.
    """
    if type(manifest) is not PrivateFixtureManifest or type(expected_identity) is not AdapterIdentity:
        raise ImportProblem("Invalid private fixture review request")
    manifest.__post_init__()
    expected_identity.__post_init__()
    if manifest.identity != expected_identity:
        raise ImportProblem("Private fixture review identity requires explicit review")
    blocked = []
    for name, code in (
        ("owner_approved", "owner_approval_required"),
        ("anonymization_reviewed", "anonymization_review_required"),
        ("dynamic_keys_reviewed", "dynamic_key_review_required"),
        ("attachments_removed", "attachment_exclusion_required"),
        ("references_verified", "reference_validation_required"),
        ("source_types_preserved", "source_type_preservation_required"),
        ("parser_reviewed", "pure_parser_review_required"),
        ("pipeline_inert_reviewed", "inert_pipeline_review_required"),
    ):
        if not getattr(manifest, name):
            blocked.append(code)
    if not manifest.raw_id_types:
        blocked.append("source_id_type_review_required")
    if "integer" in manifest.raw_id_types:
        blocked.append("raw_id_provenance_contract_required")
    if manifest.timestamp_representation == "unverified":
        blocked.append("timestamp_type_review_required")
    elif manifest.timestamp_representation != "aware_iso":
        blocked.append("raw_timestamp_provenance_contract_required")
    if manifest.timestamp_precision == "unverified":
        blocked.append("timestamp_precision_review_required")
    if manifest.branches == "unverified":
        blocked.append("branch_classification_required")
    elif manifest.branches == "preserved":
        blocked.append("branch_provenance_contract_required")
    if manifest.revisions == "unverified":
        blocked.append("revision_classification_required")
    elif manifest.revisions == "preserved":
        blocked.append("revision_provenance_contract_required")
    if manifest.unknown_field_policy != "fail_closed":
        blocked.append("unknown_field_policy_required")
    return {"mode": "manifest_only", "contract_version": PREFLIGHT_VERSION,
            "provider": manifest.identity.provider, "product": manifest.identity.product,
            "review_ready": not blocked, "blocked_codes": blocked,
            "missing_records_possible": manifest.missing_records_possible,
            "gate_state": "BLOCKED", "enabled": False, "real_format_verified": False,
            "files_read": 0, "stored_records": 0,
            "required_activation_gates": ["approved_private_fixture_review", "parser_regressions",
                                          "storage_privacy_review", "windows_owner_evidence",
                                          "source_head_ci", "explicit_activation_review"]}
