"""Versioned acceptance contracts; no inferred real-provider parser is enabled."""

import hashlib
import re
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Literal, Protocol

from nexus.importers import (
    MAX_MESSAGES,
    MAX_UNCOMPRESSED_BYTES,
    Conversation,
    ImportProblem,
    Message,
    require_str,
    source_timestamp,
)

CONTRACT_VERSION = "history-adapter-contract-1"


@dataclass(frozen=True)
class AdapterIdentity:
    provider: Literal["openai", "anthropic"]
    product: Literal["consumer_chatgpt", "consumer_claude"]
    parser_version: str
    # Do not expose a private review reference through incidental debug/exception repr.
    schema_evidence_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.provider) is not str or type(self.product) is not str:
            raise ImportProblem("Invalid adapter product identity")
        if (self.provider, self.product) not in {
            ("openai", "consumer_chatgpt"), ("anthropic", "consumer_claude"),
        }:
            raise ImportProblem("Invalid adapter product identity")
        for value in (self.parser_version, self.schema_evidence_id):
            if type(value) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
                raise ImportProblem("Invalid adapter review metadata")


@dataclass(frozen=True)
class HistoryCoverage:
    complete: bool = False
    missing_records_possible: bool = True
    attachments_verified: bool = False
    branches_verified: bool = False
    revisions_verified: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, field.name)) is not bool for field in fields(self)):
            raise ImportProblem("Invalid adapter coverage classification")
        if self.complete and self.missing_records_possible:
            raise ImportProblem("Contradictory adapter coverage classification")


@dataclass(frozen=True)
class ParsedHistory:
    # Normalized source data is as private as the raw payload. The default repr
    # can safely describe trust/coverage without rendering review refs or text.
    identity: AdapterIdentity = field(repr=False)
    conversations: tuple[Conversation, ...] = field(repr=False)
    coverage: HistoryCoverage
    contract_version: str = CONTRACT_VERSION
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"

    def __post_init__(self) -> None:
        if (type(self.identity) is not AdapterIdentity or type(self.coverage) is not HistoryCoverage
                or type(self.contract_version) is not str or self.contract_version != CONTRACT_VERSION
                or type(self.trust) is not str or self.trust != "untrusted_source_data"
                or type(self.conversations) is not tuple):
            raise ImportProblem("Invalid adapter result contract")


class HistoryAdapter(Protocol):
    """Pure bounded parsing; never executes text, connects accounts or writes a database.

    A future implementation must preserve verified source IDs/time representations;
    ambiguous IDs/revisions must reject the complete batch before storage. Adding a
    parser requires approved private evidence and explicit regression fixtures.
    """

    identity: AdapterIdentity

    def parse(self, payload: bytes) -> ParsedHistory: ...


class UnverifiedRealAdapter:
    """Even fabricated evidence metadata cannot activate a real parser in V1."""

    def parse(self, _payload: bytes) -> ParsedHistory:
        raise ImportProblem("Real-format adapter BLOCKED: approved schema evidence not verified")


def _normalized_text(value: object, name: str, max_length: int = 200000) -> str:
    # Normalized parser output must be inert builtin data. A str subclass can
    # override equality, hashing or encoding and evade the validation below.
    if type(value) is not str:
        raise ImportProblem("Invalid normalized text type")
    return require_str(value, name, max_length)


def dry_run_history(adapter: HistoryAdapter, payload: bytes,
                    expected_identity: AdapterIdentity) -> dict:
    """Review-only normalization check. No registry, DB, account access or evidence promotion.

    Only reviewed pure parser implementations may be supplied. This validates the
    current normalized storage contract, not a vendor's raw timestamp/graph schema.
    Private review IDs, source IDs, hashes and payloads never enter the summary.
    """
    if type(payload) is not bytes or not payload or len(payload) > MAX_UNCOMPRESSED_BYTES:
        raise ImportProblem("Invalid adapter dry-run payload")
    try:
        if type(expected_identity) is not AdapterIdentity:
            raise ImportProblem("Adapter version requires explicit review")
        expected_identity.__post_init__()
        # Keep the reviewed value independent of objects shared with a parser.
        # frozen dataclasses are not a security sandbox or a deep immutability guarantee.
        reviewed_identity = replace(expected_identity)
        parser_identity = adapter.identity
        if type(parser_identity) is not AdapterIdentity:
            raise ImportProblem("Adapter version requires explicit review")
        parser_identity.__post_init__()
        if parser_identity != reviewed_identity:
            raise ImportProblem("Adapter version requires explicit review")
        result = adapter.parse(payload)
        if type(result) is not ParsedHistory:
            raise ImportProblem("Adapter result identity mismatch")
        result.__post_init__()
        result.identity.__post_init__()
        result.coverage.__post_init__()
        final_parser_identity = adapter.identity
        if type(final_parser_identity) is not AdapterIdentity:
            raise ImportProblem("Adapter version requires explicit review")
        final_parser_identity.__post_init__()
        if result.identity != reviewed_identity or final_parser_identity != reviewed_identity:
            raise ImportProblem("Adapter result identity mismatch")
        if len(result.conversations) > 10000:
            raise ImportProblem("Adapter conversation limit exceeded")
        messages = 0
        text_bytes = 0
        conversation_ids = set()
        for conversation in result.conversations:
            if type(conversation) is not Conversation or type(conversation.messages) is not list:
                raise ImportProblem("Invalid normalized conversation")
            identity = _normalized_text(conversation.external_id, "conversation identity", 1000)
            title = _normalized_text(conversation.title, "title", 1000)
            if identity in conversation_ids:
                raise ImportProblem("Ambiguous normalized conversation identity")
            conversation_ids.add(identity)
            message_ids = set()
            text_bytes += len(title.encode("utf-8")) + len(identity.encode("utf-8"))
            for message in conversation.messages:
                messages += 1
                if messages > MAX_MESSAGES or type(message) is not Message:
                    raise ImportProblem("Invalid normalized message collection")
                message_id = _normalized_text(message.external_id, "message identity", 1000)
                role = _normalized_text(message.role, "role", 60)
                content = _normalized_text(message.content, "content")
                if message.occurred_at is not None and type(message.occurred_at) is not str:
                    raise ImportProblem("Invalid normalized timestamp type")
                source_timestamp(message.occurred_at)
                if message_id in message_ids:
                    raise ImportProblem("Ambiguous normalized message identity")
                message_ids.add(message_id)
                encoded = content.encode("utf-8")
                if (type(message.content_sha256) is not str
                        or not re.fullmatch(r"[a-f0-9]{64}", message.content_sha256)
                        or message.content_sha256 != hashlib.sha256(encoded).hexdigest()):
                    raise ImportProblem("Normalized content hash mismatch")
                text_bytes += (len(encoded) + len(message_id.encode("utf-8"))
                               + len(role.encode("utf-8")) + len(message.occurred_at or ""))
                if text_bytes > MAX_UNCOMPRESSED_BYTES:
                    raise ImportProblem("Normalized history size exceeds safety limit")
        if text_bytes > MAX_UNCOMPRESSED_BYTES:
            raise ImportProblem("Normalized history size exceeds safety limit")
        return {"mode": "contract_dry_run", "contract_version": CONTRACT_VERSION,
                "provider": result.identity.provider, "product": result.identity.product,
                "conversations": len(result.conversations), "messages": messages,
                "coverage": asdict(result.coverage), "stored_records": 0,
                "real_format_verified": False}
    except Exception:
        # A future parser's exception can contain source text, paths or IDs.
        raise ImportProblem("Adapter dry-run refused; private details omitted") from None


def real_format_gates() -> list[dict]:
    return [{"provider": provider, "product": product, "contract_version": CONTRACT_VERSION,
             "state": "BLOCKED", "enabled": False, "parser_version": None,
             "reason": "approved_anonymized_sample_required"}
            for provider, product in (("openai", "consumer_chatgpt"),
                                      ("anthropic", "consumer_claude"))]
