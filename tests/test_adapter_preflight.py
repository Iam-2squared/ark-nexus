"""Manifest-only review of invented declarations; no real sample or vendor schema."""

import json
from dataclasses import replace

import pytest

from nexus.adapter_contracts import AdapterIdentity, real_format_gates
from nexus.adapter_preflight import PrivateFixtureManifest, review_private_fixture_manifest
from nexus.importers import ImportProblem


def identity():
    return AdapterIdentity("openai", "consumer_chatgpt", "invented-1", "private-review-1")


def declared_manifest():
    return PrivateFixtureManifest(
        identity(), owner_approved=True, anonymization_reviewed=True, dynamic_keys_reviewed=True,
        attachments_removed=True, raw_id_types=("string",), timestamp_representation="aware_iso",
        timestamp_precision="subseconds", references_verified=True, source_types_preserved=True,
        branches="absent", revisions="absent", unknown_field_policy="fail_closed",
        parser_reviewed=True, pipeline_inert_reviewed=True,
    )


def test_unreviewed_manifest_is_blocked_by_each_distinct_review_requirement():
    summary = review_private_fixture_manifest(PrivateFixtureManifest(identity()), identity())
    assert summary["review_ready"] is False
    assert len(summary["blocked_codes"]) == 14
    assert "owner_approval_required" in summary["blocked_codes"]
    assert "dynamic_key_review_required" in summary["blocked_codes"]
    assert "source_id_type_review_required" in summary["blocked_codes"]
    assert summary["gate_state"] == "BLOCKED" and summary["enabled"] is False


@pytest.mark.parametrize("field", [
    "owner_approved", "anonymization_reviewed", "dynamic_keys_reviewed", "attachments_removed",
    "references_verified", "source_types_preserved", "missing_records_possible", "parser_reviewed",
    "pipeline_inert_reviewed",
])
def test_boolean_declarations_reject_truthy_strings_and_integer_permissions(field):
    for value in ("true", 1, None):
        with pytest.raises(ImportProblem):
            replace(declared_manifest(), **{field: value})


@pytest.mark.parametrize("changes", [
    {"raw_id_types": ["string"]}, {"raw_id_types": ("string", "string")},
    {"raw_id_types": (1,)}, {"raw_id_types": ("bool",)}, {"raw_id_types": ([],)},
    {"timestamp_representation": "guessed_vendor_schema"},
    {"timestamp_precision": 3}, {"branches": "ignored"}, {"revisions": "last-write-wins"},
    {"unknown_field_policy": "ignore"}, {"identity": "PRIVATE-SYNTHETIC-PATH"},
])
def test_manifest_invalid_types_unknown_fields_and_lossy_policies_are_refused(changes):
    with pytest.raises(ImportProblem) as failure:
        replace(declared_manifest(), **changes)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)


@pytest.mark.parametrize("changes,code", [
    ({"raw_id_types": ("integer",)}, "raw_id_provenance_contract_required"),
    ({"raw_id_types": ("string", "integer")}, "raw_id_provenance_contract_required"),
    ({"timestamp_representation": "epoch_number"}, "raw_timestamp_provenance_contract_required"),
    ({"timestamp_representation": "mixed"}, "raw_timestamp_provenance_contract_required"),
    ({"timestamp_precision": "unverified"}, "timestamp_precision_review_required"),
    ({"branches": "preserved"}, "branch_provenance_contract_required"),
    ({"revisions": "preserved"}, "revision_provenance_contract_required"),
])
def test_source_type_branch_and_revision_fidelity_requires_future_storage_contract(changes, code):
    manifest = replace(declared_manifest(), **changes)
    summary = review_private_fixture_manifest(manifest, identity())
    assert summary["review_ready"] is False and code in summary["blocked_codes"]
    assert summary["enabled"] is False and summary["real_format_verified"] is False


@pytest.mark.parametrize("changes", [
    {"parser_version": "invented-2"}, {"schema_evidence_id": "private-review-2"},
    {"provider": "anthropic", "product": "consumer_claude"},
])
def test_expected_product_parser_and_review_reference_must_match(changes):
    with pytest.raises(ImportProblem):
        review_private_fixture_manifest(declared_manifest(), replace(identity(), **changes))


def test_complete_declarations_do_not_read_files_execute_parser_or_promote_real_gates(monkeypatch):
    import builtins
    import socket
    import subprocess

    from nexus.store import Store

    def unexpected(*_args, **_kwargs):
        pytest.fail("A manifest-only preflight must not read files, parse or execute anything")

    monkeypatch.setattr(builtins, "open", unexpected)
    monkeypatch.setattr(socket, "create_connection", unexpected)
    monkeypatch.setattr(subprocess, "run", unexpected)
    monkeypatch.setattr(Store, "connect", unexpected)
    before = real_format_gates()
    summary = review_private_fixture_manifest(declared_manifest(), identity())
    assert summary["review_ready"] is True and summary["blocked_codes"] == []
    assert summary["gate_state"] == "BLOCKED" and summary["enabled"] is False
    assert summary["files_read"] == summary["stored_records"] == 0
    assert summary["real_format_verified"] is False
    assert "windows_owner_evidence" in summary["required_activation_gates"]
    assert "approved_private_fixture_review" in summary["required_activation_gates"]
    assert real_format_gates() == before
    assert "private-review-1" not in json.dumps(summary)
    assert "private-review-1" not in repr(declared_manifest())
    assert "invented-1" not in json.dumps(summary)


def test_defaults_keep_missing_records_possible_and_do_not_imply_record_deletion():
    manifest = declared_manifest()
    assert manifest.missing_records_possible is True
    summary = review_private_fixture_manifest(manifest, identity())
    assert summary["missing_records_possible"] is True
    assert summary["mode"] == "manifest_only" and summary["stored_records"] == 0


def test_manifest_revalidation_rejects_mutated_identity_without_private_diagnostics():
    manifest = declared_manifest()
    object.__setattr__(manifest.identity, "schema_evidence_id", "PRIVATE-SYNTHETIC/PATH")
    with pytest.raises(ImportProblem) as failure:
        review_private_fixture_manifest(manifest, identity())
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)
