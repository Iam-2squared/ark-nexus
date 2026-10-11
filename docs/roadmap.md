# ARK Nexus — Roadmap baseline

ARK Nexus is a separate repository and development track from ARK AI V1–V10.

| Version | Main focus | Completion gate | State |
|---|---|---|---|
| V1 Unified History | Authorized real ChatGPT/Claude export import, dedup, project indexing, offline search | Two current real-format fixture families, 1,000-message reimport zero duplicates, 30 search assertions | ACTIVE: authenticated synthetic import, 6-screen dashboard, integrity/recovery; real formats BLOCKED |
| V2 Multi-AI Control | Verified task dispatch with explicit approvals | Two isolated approved runs; zero unapproved writes | LOCKED |
| V3 Shared Intelligence | Source-backed tasks, decisions and AI cross-review | 20 provenance scenarios; no unsupported completions | LOCKED |
| V4 Automatic Sync | Codex / Claude Code session events; supported connectors | 95% of supported events within 60s under test; zero duplicates | LOCKED |
| V5 Autonomous Coordination | Bounded planner, reviewer, concurrency and budgets | 10 independent end-to-end scenarios; zero critical unsafe actions | LOCKED |

V1 PASS requires actual redacted provider fixtures and security evidence; synthetic-only tests are not completion evidence.

Completion criteria above are retained. [Validation](validation.md) adds a fixed 30-case mixed-language suite without removing the original 30 assertions. [Capability Matrix](capability-matrix.md) separates official support from Nexus connection/implementation state. Windows ACL evidence and owner-machine cold-start/offline checks remain open; no weighted progress percentage is claimed.
