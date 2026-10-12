# NEXT mega-batch — 2026-10-12

Repository: **Iam-2squared/ark-nexus** only. Start source
`79e56eb20a581825b0ce2392c82fc0d7127918fa`, branch
`feature/v1-unified-history-scaffold`; main
`91a493a9ffb636c85b016874f1f721685adab12e`. Latest GitHub identity, sole open
Draft PR1, no reviews/comments, clean dedicated checkout and no external Git
worktree/alternates were verified before implementation. Main is not changed.

Baseline [run38219581039](https://github.com/Iam-2squared/ark-nexus/actions/runs/38219581039)
at the exact start source passed5/5: Linux512 PASS/3 platform SKIP each,
Windows513 PASS/2 platform SKIP each, all Ruff, DOM47/build/Chromium7. These are
baseline results, not results for the new source. Final full source SHA, CI jobs,
native classifications and downloaded artifact digests are recorded separately
in [Draft PR1](https://github.com/Iam-2squared/ark-nexus/pull/1).

## Implemented / synthetic-verified changes

| Priority | Concrete change | Additive cases and initial reproduction |
| --- | --- | --- |
| P0 statement/native evidence | Bounded late UNIQUE/CHECK/trigger abort, transaction-preserved prior writes, FTS MATCH/internal checks, interruption rollback, backup/restore; disposable explicit VFS of actual Python runtime; FILE positive control; strict child-output allowlist | 38 new tests. Four mocked-child unknown/private/duplicate/missing-schema cases failed before output-boundary correction. SQL suites are new qualification work, not claims that SQLite rollback was broken |
| P1 import framing | Only POST gets8 MiB envelope/2 permits; other methods64 KiB; exact chunked coding; duplicate boundary/charset/name/filename refusal; part UTF-8/encoding agreement; rejection cleanup and subsequent permit reuse | 37 new tests; initial21 FAIL/5 PASS, then2 additional framing-whitespace FAIL before correction |
| P1 DB and copy integrity | Count invalid identities across10 logical tables; non-coercing BLOB-safe content/hash checks; invalid DB copy refusal, replaced-destination identity protection, reserved-table recovery | 20 new tests; initial14 FAIL/1 PASS, then20 PASS |
| P2 Windows acceptance | Reject duplicate PowerShell JSON keys; pure16 KiB/10-field/14-Gate owner report receipt with independently selected source HEAD and self-declared origin | 66 new tests;3 duplicate-key FAIL before correction. Producer schema/Gates and PS scripts unchanged |
| P3 disabled planning contract | Bind entire reviewed checkpoint metadata/lease; reject silent control-clock precision truncation; keep raw occurrence precision untouched | 24 new tests; initial14 FAIL/10 PASS, then24 PASS. No provider auth/dispatch authority added |
| P4 White N UI | Source, CSS/SVG, original DOM/E2E/5-width gates unchanged | DOM47/build PASS locally; Chromium7 requires new source-HEAD CI and actual image review |

**185 additive backend cases** retain all original tests, fixtures, migrations,
limits and scoring. Work default Linux/Python3.12.14/SQLite3.53.1 local full suite:
**697 PASS/3 platform SKIP** (24.45s), Ruff PASS; DOM47/build PASS.
Final OS/Python/CI results must be recorded with their actual source HEAD in PR1.
Windows-only skips remain the original platform gates; owner Gates
are NOT RUN, not pytest SKIPs or synthetic PASS.

The only workflow addition is a bounded synthetic SQLite evidence step in each
existing backend job. Existing five jobs, timeouts, commands, original browser
scenarios, artifact paths and retention are retained. No SQLite report/DB/raw
trace/key becomes a public artifact. Child failure/scope escape is an additive
step failure; unavailable native exports explicitly produce NOT RUN.

## P0 runtime observations and unqualified surfaces

See [full native/SQL and storage-surface matrix](sqlite-statement-observation.md).
The Work default builtin Python3.12.14/SQLite3.53.1 has unavailable VFS exports:
native captured=false / capability_unavailable / NOT RUN. A separately labelled
installed Python3.12.3/SQLite3.45.1 actually executes Nexus code and its own
`sqlite3` connections; the explicit observer is reached. At2,048 rows, FILE/WAL
positive control captured2 unnamed statement-journal opens and1,968 write calls
(4,157,400 requested bytes). The same MEMORY workloads captured zero subjournal
opens. Named outside-root count0, callback errors0, default VFS unchanged.

This is runtime-specific VFS observation, not OS syscall capture, proof of unnamed
physical path placement, all-query coverage, owner runtime qualification or swap
protection. Native seed/backup connections are not captured. All-path statement
journal/private storage qualification remains BLOCKED. No production journal
mode OFF/MEMORY, synchronous OFF, global temp directory, OS ACL, kernel driver,
ptrace escalation or original/default VFS replacement is introduced.

## Retained unresolved observation

The earlier10k anomaly **recurred once** in the DB-related combined suite:
122 PASS/1 FAIL/1 SKIP. After a preceding valid overview/integrity observation,
the failing synthetic file showed sources/conversations/messages/imports/FTS0,
source-events/audit2, FK violations2. Read-only inspection by both the Work
runtime and separate SQLite3.45.1 confirmed the persisted discrepancy. The file
is retained locally and never uploaded. Cause remains **unresolved**.

Three new10k benchmark roots, the frozen single test, a21-test sequence with116
count-only connection observations, and the later relevant suite123 PASS/1
platform SKIP did not reproduce it. Those successes do not establish a fix.
No frozen expectation/index/data was rebuilt, deleted, relaxed or skipped to
hide the observation. See [DB evidence](db-integrity-next.md) for conditions and
measurements. No50k target or owner performance qualification is invented.

## Remaining external gates / prohibited operations

- Consumer ChatGPT and Consumer Claude: approved anonymized real samples absent;
  adapters disabled/BLOCKED. No guessed real parser or HTTP registration.
- Owner Windows offline cold start, browser, other-user denial and normal-profile
  ACL: no owner evidence, NOT RUN. Runner report8 synthetic PASS/6 NOT RUN cannot
  become owner PASS. New receipt acceptance is pure validation, not authentication.
- Six connectors: disconnected and execution-disabled; auth/provider calls/cost0.
  Planning remains simulation only; V2–V5 LOCKED.
- SQLite plaintext, crash/unlink/cache/swap/pagefile/remanence and actual-profile
  protection remain unqualified. **Private imports forbidden; official V1 BLOCKED**.
- Retention/encryption/destructive deletion/automatic dispatch are not enabled.
- Other repository/project writes, main commit/push/merge, force-push, paid API,
  external AI login and private-data transmission:0.

The four synthetic browser PNGs and the unchanged Windows report schema are the
existing artifact allowlist. Latest CI source/merge SHA, archive hashes, member
names and image review must be checked after the commit. This document does not
declare unseen CI or owner results successful.
