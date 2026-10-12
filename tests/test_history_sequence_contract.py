"""Bounded metadata-only page review; no provider calls or persisted cursors."""

import json
import os
import socket
import sqlite3
import subprocess
from dataclasses import replace

import pytest

from nexus import connector_contracts as contract

NOW = "2026-01-01T12:00:00+00:00"


def scope(provider="openai", product="codex_local"):
    return contract.SourceScope(provider, product, "synthetic-source", "synthetic-account",
                                "synthetic-project")


def page(number, token=None, *, source=None, parser="synthetic-1", identity=None):
    source = source or scope()
    event = contract.SourceObservation(source, identity or f"synthetic-{number}", None,
                                       NOW, "history_record")
    cursor = contract.HistoryCursor(source, parser, token, NOW) if token else None
    return contract.HistoryBatch(source, parser, (event,), cursor, complete=cursor is None)


@pytest.mark.parametrize("provider,product", sorted(contract.PRODUCT_NAMESPACES))
def test_sequence_review_stays_offline_and_disabled_for_each_product(monkeypatch, provider, product):
    def denied(*_args, **_kwargs):
        pytest.fail("Contract review must remain memory-only")

    for module, attribute in ((socket, "socket"), (subprocess, "Popen"),
                              (sqlite3, "connect"), (os, "open")):
        monkeypatch.setattr(module, attribute, denied)
    source = scope(provider, product)
    result = contract.review_history_sequence((page(1, "PRIVATE-SYNTHETIC", source=source),
                                               page(2, source=source)), source, "synthetic-1")
    assert result["pages"] == result["events"] == 2 and result["complete"] is True
    assert result["connected"] is result["execution_enabled"] is False
    assert result["provider_calls"] == result["cost_microunits"] == result["stored_records"] == 0
    assert "PRIVATE-SYNTHETIC" not in json.dumps(result)


@pytest.mark.parametrize("pages", [
    (page(1, "a"), page(2, "b"), page(3, "a")),
    (page(1, "a", identity="same"), page(2, identity="same")),
    (page(1), page(2)),
    (page(1, "a"), page(2, source=replace(scope(), project_ref="different"))),
    (page(1, "a"), page(2, parser="different-1")),
    (),
    [page(1)],
    (page(1, "a"),) * 65,
])
def test_sequence_rejects_loops_repeated_ids_wrong_bindings_and_unbounded_pages(pages):
    with pytest.raises(contract.PlanningProblem) as raised:
        contract.review_history_sequence(pages, scope(), "synthetic-1")
    assert str(raised.value) == "Connector planning contract refused; private details omitted"


def test_previous_checkpoint_participates_in_non_adjacent_loop_detection():
    previous = contract.HistoryCursor(scope(), "synthetic-1", "a", NOW)
    with pytest.raises(contract.PlanningProblem):
        contract.review_history_sequence((page(1, "b"), page(2, "a")), scope(), "synthetic-1",
                                         previous_cursor=previous)


def test_sequence_keeps_an_incomplete_terminal_snapshot_incomplete():
    result = contract.review_history_sequence((replace(page(1), complete=False),),
                                              scope(), "synthetic-1")
    assert result["complete"] is False and result["has_next_cursor"] is False


def test_total_event_budget_cannot_be_evaded_with_multiple_small_pages():
    def many(start, count, token):
        events = tuple(contract.SourceObservation(scope(), f"synthetic-{index}", None, NOW,
                                                 "history_record")
                       for index in range(start, start + count))
        cursor = contract.HistoryCursor(scope(), "synthetic-1", token, NOW)
        return contract.HistoryBatch(scope(), "synthetic-1", events, cursor)

    with pytest.raises(contract.PlanningProblem):
        contract.review_history_sequence((many(0, 600, "a"), many(600, 401, "b")),
                                         scope(), "synthetic-1")
