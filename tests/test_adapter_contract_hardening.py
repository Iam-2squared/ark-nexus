"""Adversarial normalized objects only; no guessed provider export fields."""

import hashlib
from dataclasses import replace

import pytest

from nexus.adapter_contracts import (
    CONTRACT_VERSION,
    AdapterIdentity,
    HistoryCoverage,
    ParsedHistory,
    dry_run_history,
)
from nexus.importers import Conversation, ImportProblem, Message


class EqualToAnything:
    def __eq__(self, _other):
        return True

    def __ne__(self, _other):
        return False


class TextSubclass(str):
    pass


def invented_history():
    identity = AdapterIdentity("openai", "consumer_chatgpt", "invented-1", "review-1")
    body = "日本語 synthetic"
    message = Message("message-1", "user", body, None, hashlib.sha256(body.encode()).hexdigest())
    return ParsedHistory(identity, (Conversation("thread-1", "synthetic", [message]),),
                         HistoryCoverage())


class ObjectParser:
    def __init__(self, result):
        self.result = result
        self.identity = result.identity
        self.calls = 0

    def parse(self, _payload):
        self.calls += 1
        return self.result


def test_non_identity_equal_object_rejected_before_parser_runs():
    result = invented_history()
    parser = ObjectParser(result)
    parser.identity = EqualToAnything()
    with pytest.raises(ImportProblem):
        dry_run_history(parser, b"invented-input", result.identity)
    assert parser.calls == 0


def test_mutated_expected_identity_rejected_before_parser_runs():
    result = invented_history()
    parser = ObjectParser(result)
    object.__setattr__(result.identity, "parser_version", "PRIVATE-SYNTHETIC/PATH")
    with pytest.raises(ImportProblem) as failure:
        dry_run_history(parser, b"invented-input", result.identity)
    assert parser.calls == 0
    assert "PRIVATE-SYNTHETIC" not in str(failure.value)


def test_parser_cannot_change_the_expected_review_by_mutating_an_aliased_identity():
    result = invented_history()

    class MutatingParser(ObjectParser):
        def parse(self, _payload):
            object.__setattr__(self.identity, "parser_version", "invented-2")
            return self.result

    with pytest.raises(ImportProblem):
        dry_run_history(MutatingParser(result), b"invented-input", result.identity)


@pytest.mark.parametrize("field", ["contract_version", "trust"])
def test_contract_markers_require_plain_strings(field):
    result = invented_history()
    with pytest.raises(ImportProblem):
        replace(result, **{field: EqualToAnything()})


@pytest.mark.parametrize("field", ["parser_version", "schema_evidence_id"])
def test_adapter_metadata_requires_plain_strings(field):
    identity = invented_history().identity
    with pytest.raises(ImportProblem):
        replace(identity, **{field: TextSubclass("invented-1")})


@pytest.mark.parametrize("field", ["external_id", "role", "content", "occurred_at"])
def test_normalized_message_fields_reject_behavioral_string_subclasses(field):
    result = invented_history()
    conversation = result.conversations[0]
    message = conversation.messages[0]
    values = {"external_id": "message-1", "role": "user", "content": message.content,
              "occurred_at": "2026-01-01T00:00:00+00:00"}
    message = replace(message, **{field: TextSubclass(values[field])})
    result = replace(result, conversations=(replace(conversation, messages=[message]),))
    with pytest.raises(ImportProblem):
        dry_run_history(ObjectParser(result), b"invented-input", result.identity)


@pytest.mark.parametrize("field", ["external_id", "title"])
def test_normalized_conversation_fields_require_plain_strings(field):
    result = invented_history()
    conversation = result.conversations[0]
    conversation = replace(conversation, **{field: TextSubclass(getattr(conversation, field))})
    result = replace(result, conversations=(conversation,))
    with pytest.raises(ImportProblem):
        dry_run_history(ObjectParser(result), b"invented-input", result.identity)


@pytest.mark.parametrize("value", [EqualToAnything(), 1, b"0" * 64, "F" * 64, "0" * 63])
def test_content_hash_requires_canonical_lowercase_hex(value):
    result = invented_history()
    conversation = result.conversations[0]
    message = replace(conversation.messages[0], content_sha256=value)
    result = replace(result, conversations=(replace(conversation, messages=[message]),))
    with pytest.raises(ImportProblem):
        dry_run_history(ObjectParser(result), b"invented-input", result.identity)


def test_readable_iso_source_timestamp_is_preserved_without_conversion():
    result = invented_history()
    conversation = result.conversations[0]
    time = "2026-01-01T00:00:00.123456+09:00"
    message = replace(conversation.messages[0], occurred_at=time)
    result = replace(result, conversations=(replace(conversation, messages=[message]),))
    summary = dry_run_history(ObjectParser(result), b"invented-input", result.identity)
    assert result.conversations[0].messages[0].occurred_at == time
    assert summary["contract_version"] == CONTRACT_VERSION
    assert summary["stored_records"] == 0
    assert summary["real_format_verified"] is False
