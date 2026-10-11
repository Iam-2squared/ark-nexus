# Connector Capability Matrix

Checked: 2026-10-11. This describes official mechanisms found in documentation, not a connected Nexus integration. All six external connectors remain `not_connected`; task execution is disabled.

"Not verified" means this review found no verified external contract for that action. It is not a claim that a service can never provide it. History coverage is restricted to the specific information listed below.

| Service | History read | Run status | New task | Resume task | Nexus V1 |
|---|---|---|---|---|---|
| ChatGPT consumer | Manual export [1] | Not verified | Not verified | Not verified | Synthetic fixture adapter only; real schema BLOCKED |
| Claude consumer | Manual export [2] | Not verified | Not verified | Not verified | Synthetic fixture adapter only; real schema BLOCKED |
| ChatGPT Work | Not verified externally [3] | Not verified externally | Not verified externally | Not verified externally | Contract placeholder; no existing-session intervention |
| Codex Local | Documented app-server [4] | Documented | Documented | Documented | Contract placeholder; no local session/account access performed |
| Codex Cloud | Documented CLI metadata [5] | Documented list snapshot | Documented cloud exec | Not verified | Contract placeholder; full transcript retrieval not verified |
| Claude Code | Documented local SDK [6] | Documented attached run events [7] | Documented | Documented | Contract placeholder; no local session/account access performed |

| Service | Necessary authorization | Obtainable information | Synchronization delay / limitations |
|---|---|---|---|
| ChatGPT | Owner-requested, explicitly approved redacted samples | ZIP with conversation and account data; no authoritative complete field schema established | Manual; generation can take up to 7 days; plan/workspace restrictions apply |
| Claude | Owner-requested redacted samples; managed export requires organization owner | Conversation/account export; no authoritative complete message schema established | Manual; generation delay not quantified |
| Work | Separate approval before connection or any task control | Official UI supports tasks/results; external read/control surface not verified | Unknown; no inferred SLA |
| Codex Local | Approved local app-server/session scope; separately approved inference and writes | Stored threads/turns, runtime status/events; thread creation and resumption | Attached notifications; Nexus has not measured latency. Stored thread read is different from joining a running session |
| Codex Cloud | Approved authenticated CLI, plan and environment permissions | Recent task IDs, URL, status, summary, updated time; task submission | Snapshot/polling; CLI is experimental. Metadata availability does not establish full conversation access or resume |
| Claude Code | Approved local session files/SDK; separately approved inference credentials/plan | SDK session enumeration/messages; attached JSON event stream, session IDs and results | Local snapshot or attached stream; no Nexus latency evidence |

The code catalog in `src/nexus/connectors.py` keeps researched support separate from `implemented`, `connection_state`, and `execution_enabled`. `SourceEvent` carries source identity, original occurrence time, observation time, and an explicit untrusted-data marker. `HistoryPage` carries a cursor and a completeness flag that defaults to false. `ApprovedTask` is a future contract, not an authorization implementation; even a fabricated approval cannot enable the V1 `DisabledConnector`.

## Official sources

1. [ChatGPT export](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data)
2. [Claude export](https://support.claude.com/en/articles/9450526-export-your-claude-data)
3. [ChatGPT Work overview](https://learn.chatgpt.com/docs/use-chatgpt)
4. [Codex App Server](https://learn.chatgpt.com/docs/app-server): thread/list, thread/read, thread/status/changed, thread/start, turn/start, thread/resume
5. [Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli): codex cloud list --json; codex cloud exec --env
6. [Claude Code sessions](https://code.claude.com/docs/en/agent-sdk/sessions): list_sessions/get_session_messages
7. [Claude Code programmatic execution](https://code.claude.com/docs/en/headless): -p, stream-json, --resume

Do not derive consumer ChatGPT/Claude history access from a model inference API. None of these references grants access to this user's accounts.
