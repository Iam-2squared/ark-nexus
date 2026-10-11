"""Versioned acceptance contracts; no inferred real-provider parser is enabled."""

import hashlib
import re
from dataclasses import asdict, dataclass, fields
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
    schema_evidence_id: str  # Private review reference, never a raw export path or account ID.

    def __post_init__(self) -> None:
        if type(self.provider) is not str or type(self.product) is not str:
            raise ImportProblem("Invalid adapter product identity")
        if (self.provider, self.product) not in {
            ("openai", "consumer_chatgpt"), ("anthropic", "consumer_claude"),
        }:
            raise ImportProblem("Invalid adapter product identity")
        for value in (self.parser_version, self.schema_evidence_id):
            if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
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
    identity: AdapterIdentity
    conversations: tuple[Conversation, ...]
    coverage: HistoryCoverage
    contract_version: str = CONTRACT_VERSION
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"

    def __post_init__(self) -> None:
        if (type(self.identity) is not AdapterIdentity or type(self.coverage) is not HistoryCoverage
                or self.contract_version != CONTRACT_VERSION or self.trust != "untrusted_source_data"
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
        if type(expected_identity) is not AdapterIdentity or adapter.identity != expected_identity:
            raise ImportProblem("Adapter version requires explicit review")
        result = adapter.parse(payload)
        if type(result) is not ParsedHistory or result.identity != expected_identity:
            raise ImportProblem("Adapter result identity mismatch")
        result.__post_init__()
        result.identity.__post_init__()
        result.coverage.__post_init__()
        if len(result.conversations) > 10000:
            raise ImportProblem("Adapter conversation limit exceeded")
        messages = 0
        text_bytes = 0
        conversation_ids = set()
        for conversation in result.conversations:
            if type(conversation) is not Conversation or type(conversation.messages) is not list:
                raise ImportProblem("Invalid normalized conversation")
            identity = require_str(conversation.external_id, "conversation identity", 1000)
            title = require_str(conversation.title, "title", 1000)
            if identity in conversation_ids:
                raise ImportProblem("Ambiguous normalized conversation identity")
            conversation_ids.add(identity)
            message_ids = set()
            text_bytes += len(title.encode("utf-8")) + len(identity.encode("utf-8"))
            for message in conversation.messages:
                messages += 1
                if messages > MAX_MESSAGES or type(message) is not Message:
                    raise ImportProblem("Invalid normalized message collection")
                message_id = require_str(message.external_id, "message identity", 1000)
                role = require_str(message.role, "role", 60)
                content = require_str(message.content, "content")
                source_timestamp(message.occurred_at)
                if message_id in message_ids:
                    raise ImportProblem("Ambiguous normalized message identity")
                message_ids.add(message_id)
                encoded = content.encode("utf-8")
                if message.content_sha256 != hashlib.sha256(encoded).hexdigest():
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
