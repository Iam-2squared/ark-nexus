# ARK Nexus — Initial Architecture (Draft)

## Design boundary
ARK Nexus is a local-first multi-AI coordination plane. It is an independent repository, and does not import, modify or run ARK AI.

## V1
- User-controlled synthetic fixture adapter behind provider-labelled interfaces. Real ChatGPT and Claude exports deliberately rejected until validated.
- Normalized entities: source_instances, import_batches, conversations, messages, projects, source_events, tasks, evidence_links, sync_cursors and audit_log.
- Distinguish source event time (occurred_at), Nexus observation time (observed_at), source IDs, parser version, batch hash, and coverage.
- Local SQLite FTS5 search, manual project categorization, idempotent reimports, immutable message IDs. No remote service requests.
- ZIP and JSON size caps, ZIP traversal/symlink rejection, transactional imports.
- Local loopback HTTP with an owner-local bearer key for private endpoints, plus exact Host/Origin, peer, Fetch Metadata and non-simple write-header checks. Keys remain outside source control; browser sessions can lock and clear visible records.
- Request streaming limits apply before JSON/multipart parsing. Paginated records expose actual totals and next offsets; Overview/project totals use complete database counts.
- Integrity checks cover SQLite/foreign keys, search-index gaps/duplicates/staleness and message hashes. SQLite backup restores only to a new path; retention/deletion remains owner-controlled.
- Researched capabilities, active connection state and implementation status are separate fields. The future Connector protocol carries source events/cursors and approved-task contracts, but V1 execution always raises an explicit denial.
- Imported text is untrusted data; never follow embedded instructions.

## Follow-on versions
V2 controlled official API/SDK/CLI dispatch; V3 source-backed shared memory; V4 compatible event/CLI session sync; V5 bounded autonomous coordination. Different products have different capabilities. Do not claim read access to consumer ChatGPT/Claude chats or existing Work sessions via a model API.

## Open review gates
- Real-format adapters need user-authorized *redacted* current export samples; inspect formats without adding private data to public GitHub.
- Remaining private-data review: Windows ACL evidence, owner-machine offline/cold-start/browser evidence, and plaintext storage decisions. See [security and data policy](security-and-data.md).
- Current-HEAD evidence for UI build/DOM/actual-browser tests and Windows/Linux CI. See [fixed evaluation definition](validation.md).
- No release or merge without user review.
