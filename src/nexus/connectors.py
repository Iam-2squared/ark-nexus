"""Future connector contracts and researched support; all execution stays disabled in V1."""

from dataclasses import asdict, dataclass
from typing import Literal, Protocol

Support = Literal["documented", "manual_export", "not_verified"]


@dataclass(frozen=True)
class Capability:
    history: Support
    status: Support
    dispatch_new: Support
    resume_existing: Support


@dataclass(frozen=True)
class ConnectorInfo:
    id: str
    label: str
    official: Capability
    permissions: str
    obtainable: str
    latency: str
    references: tuple[str, ...]
    connection_state: str = "not_connected"
    implemented: bool = False
    execution_enabled: bool = False


CATALOG = (
    ConnectorInfo("chatgpt", "ChatGPT", Capability("manual_export", "not_verified", "not_verified", "not_verified"),
                  "Owner-requested, redacted export only; no account connection",
                  "Exported chat/account data; exact message schema unvalidated",
                  "Manual; export generation can take up to 7 days",
                  ("https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data",)),
    ConnectorInfo("claude", "Claude", Capability("manual_export", "not_verified", "not_verified", "not_verified"),
                  "Owner-requested, redacted export only; organization owner for managed exports",
                  "Exported conversation/account data; exact message schema unvalidated",
                  "Manual; generation delay unspecified",
                  ("https://support.claude.com/en/articles/9450526-export-your-claude-data",)),
    ConnectorInfo("chatgpt_work", "ChatGPT Work",
                  Capability("not_verified", "not_verified", "not_verified", "not_verified"),
                  "Separate approval required; no public external session-control contract verified",
                  "Work UI shows tasks/results; external history/status/dispatch not verified",
                  "Unknown; no polling or task injection",
                  ("https://learn.chatgpt.com/docs/use-chatgpt",)),
    ConnectorInfo("codex_local", "Codex Local",
                  Capability("documented", "documented", "documented", "documented"),
                  "Approved local app-server/session scope; separate approval for inference and writes",
                  "thread/list, thread/read, thread/status/changed, thread/start, turn/start, thread/resume",
                  "Event-driven while attached; latency has not been measured by Nexus",
                  ("https://learn.chatgpt.com/docs/app-server",)),
    ConnectorInfo("codex_cloud", "Codex Cloud",
                  Capability("documented", "documented", "documented", "not_verified"),
                  "Approved authenticated CLI and cloud environment; plan permissions",
                  "codex cloud list metadata/status/summary; cloud exec submits a task; full transcript not verified",
                  "CLI snapshot/polling; no measured sync SLA",
                  ("https://learn.chatgpt.com/docs/developer-commands?surface=cli",)),
    ConnectorInfo("claude_code", "Claude Code",
                  Capability("documented", "documented", "documented", "documented"),
                  "Approved local session files/SDK scope; inference requires separately approved credentials/plan",
                  "SDK list_sessions/get_session_messages; claude -p stream-json; --resume",
                  "Attached event stream or local snapshot; no measured sync SLA",
                  ("https://code.claude.com/docs/en/agent-sdk/sessions",
                   "https://code.claude.com/docs/en/headless")),
)


@dataclass(frozen=True)
class SourceEvent:
    source_id: str
    external_id: str
    occurred_at: str | None
    observed_at: str
    kind: str
    payload: dict
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"


@dataclass(frozen=True)
class HistoryPage:
    events: tuple[SourceEvent, ...]
    cursor: str | None
    complete: bool = False


@dataclass(frozen=True)
class ApprovedTask:
    source_id: str
    objective: str
    approval_id: str
    allowed_repository: str
    session_id: str | None = None


class Connector(Protocol):
    """A future implementation must recheck grants, source and approval before any execution."""

    def read_history(self, cursor: str | None = None) -> HistoryPage: ...
    def read_status(self, session_id: str) -> dict: ...
    def dispatch_new(self, request: ApprovedTask) -> str: ...
    def resume_existing(self, request: ApprovedTask) -> str: ...


class DisabledConnector:
    """No credentials, subprocesses, network traffic or provider state changes."""

    def read_history(self, cursor: str | None = None) -> HistoryPage:
        raise PermissionError("External connector is not connected in V1")

    def read_status(self, session_id: str) -> dict:
        raise PermissionError("External connector is not connected in V1")

    def dispatch_new(self, request: ApprovedTask) -> str:
        raise PermissionError("AI execution is disabled in V1")

    def resume_existing(self, request: ApprovedTask) -> str:
        raise PermissionError("AI execution is disabled in V1")


def connection_catalog() -> list[dict]:
    products = {"chatgpt": ("openai", "consumer_chatgpt"),
                "claude": ("anthropic", "consumer_claude"),
                "chatgpt_work": ("openai", "chatgpt_work"),
                "codex_local": ("openai", "codex_local"),
                "codex_cloud": ("openai", "codex_cloud"),
                "claude_code": ("anthropic", "claude_code")}
    return [{**asdict(item), "provider": products[item.id][0], "product": products[item.id][1],
             "capabilities": {
                 "manual_export": "documented" if item.id in {"chatgpt", "claude"} else "not_verified",
                 "event_monitor": "documented" if item.id in {"codex_local", "claude_code"}
                 else "not_verified", "dispatch_new": item.official.dispatch_new,
                 "resume_existing": item.official.resume_existing},
             "not_connected_reason": "Approved real-format sample not provided"
             if item.id in {"chatgpt", "claude"} else "Nexus V1 connector is not implemented",
             "freshness": "no_observations", "checked_at": "2026-10-11"} for item in CATALOG]
