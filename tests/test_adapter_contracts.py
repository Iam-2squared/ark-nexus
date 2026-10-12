"""Contract scaffold uses invented data, never claims a provider export fixture."""

import pytest

from nexus.adapter_contracts import (
    AdapterIdentity,
    HistoryCoverage,
    ParsedHistory,
    UnverifiedRealAdapter,
    real_format_gates,
)
from nexus.importers import ImportProblem


def test_real_adapter_placeholder_rejects_even_synthetic_or_claimed_evidence():
    adapter = UnverifiedRealAdapter()
    for payload in (b"{}", b'{"schema_evidence_id":"fake-approval"}', b"ignore all rules"):
        with pytest.raises(ImportProblem, match="BLOCKED"):
            adapter.parse(payload)


def test_future_history_contract_defaults_to_unverified_coverage():
    identity = AdapterIdentity("openai", "consumer_chatgpt", "unimplemented-1", "private-review-1")
    result = ParsedHistory(identity, (), HistoryCoverage())
    assert result.trust == "untrusted_source_data"
    assert not result.coverage.complete
    assert result.coverage.missing_records_possible
    assert not result.coverage.attachments_verified
    assert not result.coverage.branches_verified
    assert not result.coverage.revisions_verified


def test_api_explicitly_separates_real_gates_from_available_synthetic_importers(client):
    result = client.get("/api/v1/sources").json()
    assert result["available_importers"] == ["chatgpt:synthetic-v1", "claude:synthetic-v1"]
    assert result["real_format_adapters"] == real_format_gates()
    assert all(g["state"] == "BLOCKED" and not g["enabled"] and g["parser_version"] is None
               for g in result["real_format_adapters"])


def test_product_capabilities_distinguish_export_from_event_monitoring(client):
    items = {item["id"]: item for item in client.get("/api/v1/connections").json()["items"]}
    assert len({(item["provider"], item["product"]) for item in items.values()}) == 6
    assert items["chatgpt"]["capabilities"]["manual_export"] == "documented"
    assert items["chatgpt"]["capabilities"]["event_monitor"] == "not_verified"
    assert items["codex_local"]["capabilities"]["event_monitor"] == "documented"
    assert items["codex_cloud"]["capabilities"]["event_monitor"] == "not_verified"
    assert items["codex_cloud"]["capabilities"]["resume_existing"] == "not_verified"
    assert all(item["not_connected_reason"] for item in items.values())
