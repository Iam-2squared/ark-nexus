# ARK Nexus — Initial Architecture (Draft)

## Design boundary
ARK Nexus is a local-first multi-AI coordination plane. It is an independent repository, and does not import, modify or run ARK AI.

## V1
- User-controlled synthetic fixture adapter behind provider-labelled interfaces. Real ChatGPT and Claude exports deliberately rejected until validated.
- Normalized entities: source_instances, import_batches, conversations, messages, projects, source_events, tasks, evidence_links, sync_cursors and audit_log.
- Distinguish source event time (occurred_at), Nexus observation time (observed_at), source IDs, parser version, batch hash, and coverage.
- Local SQLite FTS5 search, manual project categorization, idempotent reimports, immutable message IDs. No remote service requests.
- ZIP and JSON size caps, ZIP traversal/symlink rejection, transactional imports.
- Local loopback HTTP; local-only data directory outside repository. Origin check is defense-in-depth and **not remote-access authentication**.
- Imported text is untrusted data; never follow embedded instructions.

## Follow-on versions
V2 controlled official API/SDK/CLI dispatch; V3 source-backed shared memory; V4 compatible event/CLI session sync; V5 bounded autonomous coordination. Different products have different capabilities. Do not claim read access to consumer ChatGPT/Claude chats or existing Work sessions via a model API.

## Open review gates
- Real-format adapters need user-authorized *redacted* current export samples; inspect formats without adding private data to public GitHub.
- Formal security/privacy review before real import, including authorization, CSRF/DNS rebinding, database encryption choices, and retention/deletion policy.
- Evidence for full UI build and Windows/Linux CI.
- No release or merge without user review.
