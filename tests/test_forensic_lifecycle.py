"""Readonly lifecycle metadata, strict evidence, and unobserved isolation."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_data_forensics import minimal_case, watched_store

from nexus import data_forensics as forensic
from nexus.forensic_lifecycle import header_summary, pytest_lifecycle


def lifecycle_case(tmp_path):
    store, observer = watched_store(tmp_path)
    observer.connect(store.path).close()
    plugin = pytest_lifecycle(observer, forensic.FROZEN_NODE)
    plugin.pytest_collection_modifyitems([SimpleNamespace(nodeid=forensic.FROZEN_NODE)])
    plugin.boundary("fixture_setup_after")
    report = minimal_case()
    report.update(schema=2, timeline=observer.timeline, lifecycle=plugin.report())
    return store, observer, plugin, report


def test_header_is_count_only_readonly_and_does_not_include_file_identity_or_paths(tmp_path):
    store, observer, _plugin, report = lifecycle_case(tmp_path)
    before = store.path.read_bytes()
    header = header_summary(store.path, observer.identity)
    assert header["valid"] and header["page_size"] == 4096 and header["pages"] > 0
    assert store.path.read_bytes() == before
    assert str(store.path) not in json.dumps(report)
    forensic.validate_case(report)


def test_current_collection_digest_and_anonymous_position_never_claim_historical_order(tmp_path):
    _store, _observer, plugin, _report = lifecycle_case(tmp_path)
    payload = plugin.report()
    assert payload["collection_count"] == payload["frozen_test_index"] == 1
    assert len(payload["collection_sha256"]) == 64
    assert payload["historical_order_reconstructed"] is False
    assert forensic.FROZEN_NODE not in json.dumps(payload)


def test_unbound_boundary_is_unknown_not_a_false_empty_database_claim(tmp_path):
    _store, observer = watched_store(tmp_path)
    plugin = pytest_lifecycle(observer, forensic.FROZEN_NODE)
    plugin.boundary("fixture_setup_before")
    event = plugin.events[0]
    assert event["status"] == "not_bound" and event["database_present"] is None
    assert event["main_header"] is None and observer.timeline == []


def test_unobserved_mode_never_performs_boundary_sql_or_file_reads(tmp_path, monkeypatch):
    store, observer = watched_store(tmp_path)
    observer.enabled = False
    observer.path = store.path
    monkeypatch.setattr(observer, "reopened", lambda *_args: pytest.fail("No boundary SQL"))
    plugin = pytest_lifecycle(observer, forensic.FROZEN_NODE)
    for phase in forensic.BOUNDARY_PHASES:
        plugin.boundary(phase)
    assert plugin.events == []
    assert plugin.report()["boundary_observer_enabled"] is False


@pytest.mark.parametrize("change", [
    lambda r: r["lifecycle"].update({"private_path": "PRIVATE-SYNTHETIC"}),
    lambda r: r["lifecycle"].update({"collection_count": True}),
    lambda r: r["lifecycle"].update({"collection_sha256": "PRIVATE-SYNTHETIC"}),
    lambda r: r["lifecycle"].update({"historical_order_reconstructed": True}),
    lambda r: r["lifecycle"].update({"boundary_observer_enabled": False}),
    lambda r: r["lifecycle"]["events"][0].update({"sequence": 0}),
    lambda r: r["lifecycle"]["events"][0].update({"phase": "PRIVATE-SYNTHETIC"}),
    lambda r: r["lifecycle"]["events"][0].update({"snapshot_sequence": 999}),
    lambda r: r["lifecycle"]["events"][0].update({"commit_boundary_sequence": True}),
    lambda r: r["lifecycle"]["events"][0]["main_header"].update({"private": "PRIVATE-SYNTHETIC"}),
    lambda r: r["lifecycle"]["events"][0]["main_header"].update({"pages": True}),
])
def test_lifecycle_fields_cannot_forward_private_data_or_forge_scope(tmp_path, change):
    _store, _observer, _plugin, report = lifecycle_case(tmp_path)
    changed = deepcopy(report)
    change(changed)
    with pytest.raises(forensic.ForensicsProblem) as raised:
        forensic.validate_case(changed)
    assert "PRIVATE-SYNTHETIC" not in str(raised.value)


def test_boundary_budget_fails_instead_of_growing_or_erasing_evidence(tmp_path):
    _store, observer, plugin, _report = lifecycle_case(tmp_path)
    for _ in range(40):
        plugin.boundary("test_call_after")
    assert len(plugin.events) == 32 and observer.capped is True


@pytest.mark.parametrize("change", [
    lambda r: r["lifecycle"].update({"events": []}),
    lambda r: r["lifecycle"].update({"frozen_test_index": None}),
    lambda r: r["lifecycle"].update({"collection_sha256": None}),
])
def test_comparison_cannot_qualify_missing_boundaries_or_unbound_collection(tmp_path, change):
    _store, _observer, _plugin, report = lifecycle_case(tmp_path)
    change(report)
    checks = forensic.comparison_checks(report)
    assert checks.get("lifecycle_complete") is False
