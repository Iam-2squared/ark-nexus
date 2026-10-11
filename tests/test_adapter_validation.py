"""Invented contract values, not guessed ChatGPT/Claude schemas or real fixtures."""

import hashlib
import json
from dataclasses import replace

import pytest

from nexus.adapter_contracts import (
    AdapterIdentity,
    HistoryCoverage,
    ParsedHistory,
    UnverifiedRealAdapter,
    dry_run_history,
    real_format_gates,
)
from nexus.importers import MAX_UNCOMPRESSED_BYTES, Conversation, ImportProblem, Message


@pytest.mark.parametrize("provider,product", [
    ("openai", "consumer_claude"), ("anthropic", "consumer_chatgpt"),
    ("openai", "codex_cloud"), ("unknown", "consumer_chatgpt"),
])
def test_contract_rejects_mismatched_product(provider, product):
    with pytest.raises(ImportProblem):
        AdapterIdentity(provider, product, "parser-1", "private-review-1")


@pytest.mark.parametrize("provider,product", [(None, "consumer_chatgpt"),
                                            ("openai", ["consumer_chatgpt"])])
def test_contract_rejects_non_string_product_without_raw_type_error(provider, product):
    with pytest.raises(ImportProblem):
        AdapterIdentity(provider, product, "parser-1", "private-review-1")


@pytest.mark.parametrize("field,value", [
    ("parser_version", ""), ("parser_version", "PRIVATE-SYNTHETIC/PATH"),
    ("schema_evidence_id", ""), ("schema_evidence_id", "C:\\PRIVATE-SYNTHETIC"),
])
def test_contract_metadata_rejected_without_echoing_private_values(field, value):
    values = {"provider": "openai", "product": "consumer_chatgpt",
              "parser_version": "parser-1", "schema_evidence_id": "private-review-1"}
    values[field] = value
    with pytest.raises(ImportProblem) as failure:
        AdapterIdentity(**values)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)


@pytest.mark.parametrize("kwargs", [
    {"complete": "false"}, {"attachments_verified": 1},
    {"complete": True, "missing_records_possible": True},
])
def test_contract_refuses_ambiguous_or_contradictory_coverage(kwargs):
    with pytest.raises(ImportProblem):
        HistoryCoverage(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"contract_version": "future-unknown"}, {"trust": "trusted-instructions"},
])
def test_parsed_history_refuses_unrecognized_version_and_trust(kwargs):
    identity = AdapterIdentity("openai", "consumer_chatgpt", "parser-1", "private-review-1")
    with pytest.raises(ImportProblem):
        ParsedHistory(identity, (), HistoryCoverage(), **kwargs)


def history():
    content = "日本語 PRIVATE-SYNTHETIC-BODY <script>ignore rules</script>"
    message = Message("PRIVATE-SYNTHETIC-ID", "user", content,
                      "2026-01-01T00:00:00+09:00", hashlib.sha256(content.encode()).hexdigest())
    identity = AdapterIdentity("openai", "consumer_chatgpt", "invented-contract-1", "private-review-1")
    return ParsedHistory(identity, (Conversation("PRIVATE-SYNTHETIC-THREAD", "synthetic", [message]),),
                         HistoryCoverage())


class InventedParser:
    """Returns invented normalized objects. This has no vendor-schema implementation."""

    def __init__(self, result):
        self.result = result
        self.identity = result.identity

    def parse(self, _payload):
        return self.result


def test_dry_run_returns_counts_only_and_cannot_write_execute_or_promote_real_gates(
    tmp_path, monkeypatch,
):
    import socket
    import subprocess

    from nexus.store import Store

    def unexpected(*_args, **_kwargs):
        pytest.fail("A contract dry run must not access DB, network or commands")

    monkeypatch.setattr(Store, "connect", unexpected)
    monkeypatch.setattr(socket, "create_connection", unexpected)
    monkeypatch.setattr(subprocess, "run", unexpected)
    before = real_format_gates()
    result = history()
    summary = dry_run_history(InventedParser(result), b"invented-contract-input", result.identity)
    assert summary["conversations"] == summary["messages"] == 1
    assert summary["stored_records"] == 0 and summary["real_format_verified"] is False
    assert summary["coverage"]["missing_records_possible"] is True
    assert real_format_gates() == before
    assert list(tmp_path.iterdir()) == []
    for private in ("PRIVATE-SYNTHETIC", "private-review-1", "<script>", "日本語",
                    result.conversations[0].messages[0].content_sha256):
        assert private not in json.dumps(summary)


@pytest.mark.parametrize("case", ["conversation-id", "message-id", "hash", "time", "unicode"])
def test_dry_run_refuses_identity_collisions_and_invalid_normalization(case):
    result = history()
    conversation = result.conversations[0]
    message = conversation.messages[0]
    if case == "conversation-id":
        result = replace(result, conversations=(conversation, conversation))
    elif case == "message-id":
        result = replace(result, conversations=(replace(conversation, messages=[message, message]),))
    else:
        changes = {"hash": {"content_sha256": "0" * 64},
                   "time": {"occurred_at": "2026-01-01T00:00:00"},
                   "unicode": {"content": "PRIVATE-SYNTHETIC\x00"}}[case]
        result = replace(result, conversations=(replace(conversation, messages=[replace(message, **changes)]),))
    with pytest.raises(ImportProblem) as failure:
        dry_run_history(InventedParser(result), b"invented-contract-input", result.identity)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)


def test_dry_run_version_change_requires_explicit_expected_identity():
    result = history()
    old = replace(result.identity, parser_version="invented-contract-0")
    with pytest.raises(ImportProblem):
        dry_run_history(InventedParser(result), b"invented-contract-input", old)


@pytest.mark.parametrize("payload", [b"", b"x" * (MAX_UNCOMPRESSED_BYTES + 1), "text"],
                         ids=["empty", "oversized", "not-bytes"])
def test_dry_run_invalid_payload_rejected_before_parser(payload):
    class NeverCalled(InventedParser):
        def parse(self, _payload):
            pytest.fail("Invalid payload must be rejected before parsing")

    result = history()
    with pytest.raises(ImportProblem):
        dry_run_history(NeverCalled(result), payload, result.identity)


def test_dry_run_parser_exception_does_not_echo_private_details():
    class FailingParser(InventedParser):
        def parse(self, _payload):
            raise ValueError("PRIVATE-SYNTHETIC-PATH-AND-PAYLOAD")

    result = history()
    with pytest.raises(ImportProblem) as failure:
        dry_run_history(FailingParser(result), b"invented-contract-input", result.identity)
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)
    assert failure.value.__suppress_context__ is True


def test_dry_run_cannot_activate_disabled_real_adapter():
    result = history()
    with pytest.raises(ImportProblem):
        dry_run_history(UnverifiedRealAdapter(), b"invented-contract-input", result.identity)
    assert all(not gate["enabled"] for gate in real_format_gates())
