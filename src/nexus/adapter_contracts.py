"""Versioned acceptance contracts; no inferred real-provider parser is enabled."""

from dataclasses import dataclass
from typing import Literal, Protocol

from nexus.importers import Conversation, ImportProblem

CONTRACT_VERSION = "history-adapter-contract-1"


@dataclass(frozen=True)
class AdapterIdentity:
    provider: Literal["openai", "anthropic"]
    product: Literal["consumer_chatgpt", "consumer_claude"]
    parser_version: str
    schema_evidence_id: str  # Private review reference, never a raw export path or account ID.


@dataclass(frozen=True)
class HistoryCoverage:
    complete: bool = False
    missing_records_possible: bool = True
    attachments_verified: bool = False
    branches_verified: bool = False
    revisions_verified: bool = False


@dataclass(frozen=True)
class ParsedHistory:
    identity: AdapterIdentity
    conversations: tuple[Conversation, ...]
    coverage: HistoryCoverage
    contract_version: str = CONTRACT_VERSION
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"


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


def real_format_gates() -> list[dict]:
    return [{"provider": provider, "product": product, "contract_version": CONTRACT_VERSION,
             "state": "BLOCKED", "enabled": False, "parser_version": None,
             "reason": "approved_anonymized_sample_required"}
            for provider, product in (("openai", "consumer_chatgpt"),
                                      ("anthropic", "consumer_claude"))]
