# Persisted-state / storage NEXT batch — 2026-10-12

Repository: **Iam-2squared/ark-nexus** only. Start source
`f6650024ac254ddc2e68104ce851fdf40f918b09`; main
`91a493a9ffb636c85b016874f1f721685adab12e`. Sole open PR #1 was
Draft/unmerged, with no competing open PR/review/comment at the fresh start.
Baseline run **38254117100** was 5/5 success: Linux878/3 platform SKIP,
Windows879/2 platform SKIP, Ruff4, DOM47, build and Chromium7. These are
**baseline only**, not results for the changed source. Final source/merge SHA,
job results and artifact receipts belong in the current Draft PR body.

**10k: UNRESOLVED / OPEN / BLOCKED. No root-cause repair is claimed.
Official V1 BLOCKED; private export use forbidden; V2–V5 LOCKED.**

## P0 — retained evidence and falsifiable hypotheses

The retained synthetic anomaly was read again without modification using
`mode=ro&immutable=1`, query-only and MEMORY TEMP. Python3.12.14/SQLite3.53.1
and installed Python3.12.3/SQLite3.45.1 agreed: core source/conversation/message/
import/FTS counts0; source-events2/audits2/FK errors2; migrations2;
SQLite integrity `ok`; main147,456 bytes/36 pages/freelist0/change counter1/
schema cookie24; sidecars absent at these reads. Internal main bytes/hash and
file/parent identity comparisons were unchanged. No repair, VACUUM, REINDEX,
copy-over, rename or evidence cleanup was performed. Absence of sidecars now
does not prove absence earlier. Raw DB, path, identities and digests are not
published. See the [previous controls](forensics-2026-10-12.md).

Historical assertion order establishes a successful overview/integrity and
100-conversation paging before the first fixed Japanese search returned zero.
The exact original 122-pass collection, file identity and transaction timeline
were not captured and cannot be reconstructed from present collections or
directory timestamps. Expected commit/close behavior in source code is not a
measurement of that historical event. No current CI success closes it.

| Candidate | Discriminating prediction in a future failure | What current evidence does / does not exclude |
| --- | --- | --- |
| Main/parent replacement or reinitialization | Identity equality changes, or header regresses near reopen/boundary | Fresh-run equality excludes observed cooperative replacement only; ABA/same-user race remains |
| Fixture setup/teardown or test-order interaction | Counts/header change across fixture/test boundaries; collection differs | Current collection digest/index records the current order only; exact old order unavailable |
| Copy/restore source-destination confusion or old snapshot | Main identity/counts disagree with committed-close/reopen snapshot | Reviewed copy-to-new-path boundaries and fresh comparisons do not explain historical state |
| Commit/rollback/close visibility or other writer | Transaction/count change aligns with a measured boundary | Single-run anonymous connection/commit-boundary sequences improve localization; historical writer unknown |
| WAL/rollback/SHM visibility | Sidecar/SQL/header observations differ across snapshots | Header is a separate readonly sample, not an atomic WAL/SQL snapshot; no physical syscall capture |
| FTS-only/query failure | Core tables retain10k while search index differs | Retained core counts0 contradict an FTS-only explanation of the retained state; an earlier query failure followed by mutation remains possible |
| Observer timing changes manifestation | Instrumented and post-exit-only modes differ | Paired finite comparisons help; successful runs cannot exclude intermittent behavior |

### Additional child-only diagnostics

The unchanged fixed 10k test/fixture is not wrapped, replaced, reordered or
finalized by the new plugin. Pytest hooks add nine fixed boundary events around
setup, the `client` fixture, call and teardown. Collection metadata contains
count, anonymous fixed-test position and SHA-256 of **current public synthetic
node IDs**; no node IDs, parameter values, source/account IDs or private names
are serialized. `historical_order_reconstructed=false` is mandatory.

Each captured boundary references a count-only timeline snapshot. Counts for
eight tables use one SELECT; FK count, transaction state, MEMORY configuration,
journal class and sidecar booleans remain separate observations. Readonly main
header sampling exposes only byte/page/freelist/counter/schema integers after
internal file/parent checks. A header is not a transaction digest, WAL contents,
physical pathname or atomic proof against same-user races.

Connection `commit`/`rollback`/`close`, exact known transaction commands through
`Connection.execute`, and native context-manager exit now record boundaries.
SQL and arguments are forwarded unchanged; context-manager success/error and
non-closing behavior are preserved. The anonymous commit-boundary counter is
an API-boundary count, **not** a count of durable commits. Cursor-only/arbitrary
SQL transaction forms and filesystem syscalls are not a complete native trace.

Three missing-boundary/collection regressions failed before the new stricter
comparison checks. Eight earlier additive cases reproduced unobserved SQL/
context-manager boundaries and accepted sequence reuse/gaps. Child schema2 adds
strict lifecycle fields; old schema1 receipts remain readable. Schema2 success
requires a bound current collection and all nine instrumented boundaries.
The 32-boundary/4,096-checkpoint/512-connection limits remain finite; any cap,
observer failure, changed identity, FK error or committed-close difference fails.
Unobserved mode does **no** boundary SQL/file reads or connection subclassing;
it retains current collection metadata and post-exit readonly final counts.

### Finite development comparisons

Linux x86_64, Python3.12.14/builtin SQLite3.53.1, reviewed working tree based on
the start source (clean=false). One trial per scope/mode, six sequential children,
new roots only, original150-second per-child limit unchanged. Related is the
documented seven-module set, not reconstructed historical order.

| Current scope | Observed | Unobserved |
| --- | --- | --- |
| Single frozen10k | 1 PASS,816 checkpoints/9 boundaries | 1 PASS,1 final checkpoint/0 boundaries |
| Related seven modules | 89 PASS/1 platform SKIP,816/9 | 89 PASS/1 platform SKIP,1/0 |
| Full suite | 969 PASS/3 platform SKIP,816/9 | 969 PASS/3 platform SKIP,1/0 |

Every scope retained source/conversation/message/import/FTS/event/audit/migration
counts1/100/10000/2/10000/2/2/2, FK0 and main/parent identity. Instrumented scopes
had116 watched connections,116 successful commit API boundaries, zero observer
errors/core DELETE/core DROP preparations and equal committed-close/reopen counts.
Post-call and teardown header/count samples did not regress in these runs.
One single-run main-header example progressed36→2156 pages and counter1→3;
allocation varies with generated IDs, so page counts are not a new fixed scorer.
**Non-reproduction is not root-cause evidence.** These working-tree runs do not
replace final source-HEAD matrix CI.

## Independent corrections and contract work

| Area | Reproduction / change | New tests |
| --- | --- | ---: |
| P0 diagnostic transaction/sequence coverage | Four missing-boundary and four sequence refusals failed before correction | 8 |
| P0 lifecycle/schema2 | Readonly headers, hook isolation, strict private-field/type refusal, limits, collection/boundary qualification | 19 |
| P1 corrupt unreferenced IDs | NULL/empty/NUL/BLOB project IDs passed FK checks and page reads; four public routes now refuse fixed503 without repair | 16 |
| P3 ZIP local/central mismatch | Four codecs × CRC/compressed/decoded contradictions were accepted201; non-descriptor local/ZIP64 values now require exact central agreement before decoding | 12 |
| P3 ZIP descriptor follow-up | Four codecs × ordinary/ZIP64 × CRC/size/missing descriptor refusals; valid unsigned and signature-valued CRC controls | 44 |
| P2 modified-page DELETE experiment | Bounded prior UPDATE plus late CHECK abort, reopen/FTS/FK/hash equality, strict counters/private scope/limits | 19 |
| P4 page-sequence contract | New memory-only metadata review rejects A→B→A cursor loops, repeated IDs, wrong scope/parser, premature terminal pages and bounded-page/event overflow | 17 |
| **Total additive** | No old test, fixture, migration, scorer, timeout, skip, UI or CI assertion relaxed | **135** |

The ZIP proof was rerun against the exact committed start-version importer in
an isolated process with required synthetic account metadata. All12 correct
requests returned201 before the parser change, then422 `Invalid ZIP archive`
after it; no source/message/import rows were inserted on rejection. An initial
new test omitted required account metadata and received an unrelated field422;
that test-construction error is not counted as a vulnerability. Existing valid
ordinary/data-descriptor/ZIP64/prefixed four-codec controls remain unchanged.

The first source96546c32a8707f19f568061c843248945e4a961d completed CI5/5
(run38267126218; Linux969/3, Windows970/2, DOM47/build/Chromium7) before this
independent descriptor follow-up. All four matrix native logs captured the new
modified-page DELETE FILE1/556/1,201,300 and MEMORY0; original WAL remained
FILE2/1,968/4,157,400 and MEMORY0. Those results are **not** final-head evidence
for the subsequent parser change. Final source/run must be checked again.

An isolated process using that exact committed importer accepted all40 descriptor
requests201:32 contradictions/missing-descriptor cases failed their new refusal
assertions and8 valid unsigned controls passed. A single ordinary CRC mismatch
also explicitly reproduced201 versus expected422. The fixed decoder validates
bounded mandatory descriptor fields against the central directory before parsing
content. It supports optional signatures, ordinary/ZIP64 widths, and a CRC equal
to the signature constant; bytes beyond the stdlib-checked entry boundary cannot
satisfy a descriptor. Valid descriptors still import; invalid ones return fixed422
without any source/import/message writes. The new file has44 additive tests;
the original ZIP fixtures and existing codec/stream/limits remain unchanged.

The ID guard reuses the existing deep-report predicate in the same active page
snapshot. It does not hash text/copy FTS for page requests and does not enable
reserved tables. This independent refusal defect is **not** the 10k root cause.
The sequence contract has at most64 pages and1,000 distinct event IDs in memory,
no persisted cursor/revision/ledger/exactly-once claim, no new API endpoint,
connected=false, execution_enabled=false, calls0/cost0. The17 pre-implementation
failures describe a new contract, not17 bugs in a live connector.

## P2 — same-runtime modified-page DELETE control

The original clean-page DELETE workload remains unchanged and still has
`NOT RUN / positive_control_not_observed`. Its WAL FILE control is not reused
to qualify DELETE. A separate `modified_pages_delete_control` uses the same
runtime/explicit child VFS: BEGIN; UPDATE all synthetic target rows to7; then
UPDATE those rows with a CHECK failure on the last row. The failed statement
must undo only itself and retain the prior UPDATE within the transaction.
After commit/close/reopen, logical tables, FTS MATCH/native integrity, FK and
content hashes must agree. Seed/production Store calls are not native-captured.

SQLite's [temporary-file documentation](https://www.sqlite.org/tempfiles.html)
distinguishes statement rollback from whole-transaction rollback and warns
that temporary-file behavior is not a fixed future contract. Reviewed primary
source [pager.c, version3.45.1](https://github.com/sqlite/sqlite/blob/version-3.45.1/src/pager.c)
shows savepoint/main-journal bookkeeping and `subjournalPageIfRequired`.
**Inference:** a newly journaled clean page can reuse its main-journal image;
a page already changed before the failing statement needs its intermediate
image for statement rollback. The premodified-page control tests that prediction;
it does not attribute the historical10k anomaly to SQLite.

Work Linux x86_64, installed Python3.12.3 with its own dynamic SQLite3.45.1,
2,048 rows: modified-page FILE open1/requested write calls556/bytes1,201,300;
same MEMORY open/write/bytes0. No callback error/named scope escape/default-VFS
change/alternate SQLite. This is **synthetic VFS PASS for this workload only**.
The parent probe completed in68.778 seconds including its uncaptured logical
workloads; the native child kept its existing60-second bound. An earlier parent
attempt failed with a fixed diagnostic before reaching either new modified-page
directory; its exact failure reason was not captured. It is not claimed repaired
or relabeled capability-unavailable. Final matrix CI must independently pass.

Limits remain32–8,192 rows,16 cache pages,128MiB page budget,2MiB SQLite value
limit,20-second modified-statement progress budget and native-child60 seconds.
FILE is an experimental positive control only; production MEMORY/journal mode/
synchronous/default VFS and OS/global TEMP settings are unchanged. Reports are
strict count-only fields and retain new synthetic files on failure/success.

| Surface | Status / scope |
| --- | --- |
| SQL partial rollback/reopen/FK/FTS/hash/backup | Synthetic validation only, not historical root-cause repair |
| Original WAL subjournal FILE/MEMORY | Original bounded native gate; validate final matrix logs |
| Original DELETE subjournal | NOT RUN; original FILE control did not spill |
| Modified-page DELETE subjournal | Local actual-runtime FILE writing positive control / MEMORY0; final matrix evidence required |
| TEMP/sort | MEMORY configuration and bounded logical/native observations only |
| Named main DB/journal/WAL | Root/sibling/link/identity checks, no physical syscall completeness |
| Direct experimental backup connections | Separate explicit VFS experiment, not production backup capture |
| Multipart | Existing memory-only8MiB/15s/two permits and ZIP expansion32MiB/message50k gates retained |
| OS unnamed paths/SHM mmap/unlink/crash/swap/pagefile/SSD/backup residue | NOT RUN / private-use BLOCKED; no encryption claim |
| Owner Windows normal profile ACL/offline/browser/other-user refusal | NOT RUN without reviewed owner evidence |
| Consumer ChatGPT/Claude actual formats | BLOCKED/disabled; approved anonymized samples absent |

## UI, CI and evidence boundary

White N, off-white/pale-blue shell, halo/ring and six star nodes are unchanged.
No UI/CSS/SVG/dependency/workflow change is required. Original DOM47,
Chromium7/five widths and four synthetic PNG + two anonymous Windows report
allowlist/one-day retention remain intact. Windows runner PASS does not qualify
the owner's PC. Source SHA and PR merge checkout SHA must be recorded separately;
screenshots need actual visual inspection and manifests/digests before reporting.
Different overview timestamps can change pixels; no unconditional pixel-equality
claim is made. Native/forensic JSON, DBs, journals and traces are not new artifacts.

No50k benchmark is claimed for this batch. No retroactive latency PASS threshold
is introduced. A readonly, same-connection10k **metadata-guard-only** comparison
used30 alternating-order samples per implementation: the committed start guard
median19.773ms/max57.258ms; the added-ID guard median33.685ms/max72.904ms.
This records a measured validation cost, not an import/search throughput result.
Linux x86_64/Python3.12.14/SQLite3.53.1; CPU not pinned/model not collected,
tracemalloc off/RSS unmeasured, source identity/bytes unchanged, no retroactive
performance gate. Owner follow-up remains minimal: separately approved/anonymized
small Consumer samples and reviewed report.json plus manual gate outcomes only;
never raw DB/export/console/key/SID/path. Physical-storage qualification and the
unresolved10k defect still forbid private export use even after matrix CI success.

### Local execution boundary exception

The local DOM/build commands inherited a shared npm cache outside the Nexus
checkout and generated **two npm diagnostic log files** there. Metadata audit
correlated the two completion times with those commands; no other recent cache
file was found. Therefore checkout-external local writes cannot be reported as
zero. Those logs were not read, uploaded, removed or rewritten. Local npm runs
were stopped after discovery. Any future local npm command must explicitly bind
its process-only cache/log destination to a new checked Nexus ignored root;
no persistent OS/npm configuration or shared-cache cleanup is authorized.
Other repository/project source writes, main writes, paid/provider calls,
private-data transmission and original-evidence deletion remain zero.

After the descriptor follow-up, a new checkout-local uninstrumented full suite
completed **1013 PASS / 3 platform SKIP** on Work Linux/Python3.12.14/SQLite3.53.1.
The six paired comparisons above were measured before the44 descriptor tests,
not retroactively reclassified as final-head full-suite evidence.
