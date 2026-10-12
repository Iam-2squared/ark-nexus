# 10k integrity forensics and storage qualification — 2026-10-12

Repository: **Iam-2squared/ark-nexus** only. Start source:
`18e61002a7f89bc065c296e100a574bf10ff1ac4`; main:
`91a493a9ffb636c85b016874f1f721685adab12e`. Draft PR #1 was open,
unmerged, with no competing open PR, review or comment at the fresh start.
Historical run **38235807198** passed 5/5: Linux697/3 platform SKIP,
Windows698/2 POSIX SKIP, Ruff, DOM47, build and Chromium7. Those results
are baseline evidence only; new source-HEAD CI must be recorded in Draft PR #1.

**The historical 10k persisted-state discrepancy remains OPEN / BLOCKED.
Its root cause has not been identified or corrected. Official V1 remains
BLOCKED; private imports remain forbidden; V2–V5 remain LOCKED.**

## Retained anomaly and explicit hypotheses

The original frozen test and failed synthetic file were not edited, regenerated,
repaired, vacuumed, copied over or deleted. Independent reads used
`mode=ro&immutable=1`, `query_only=ON` and memory TEMP, with main/parent identity
and main bytes checked internally before/after. Python3.12.14/SQLite3.53.1 and
Python3.12.3/SQLite3.45.1 agreed on the persisted state:

| Observation | Value |
| --- | ---: |
| Source / conversation / message / import / FTS | 0 / 0 / 0 / 0 / 0 |
| Source-event / audit / FK errors | 2 / 2 / 2 |
| Main bytes / pages / freelist | 147,456 / 36 / 0 |
| Header change counter / schema cookie | 1 / 24 |
| Migrations / SQLite integrity | 1 and 2 present / ok |
| FTS data rows / data bytes / index rows | 2 / 7 / 0 |
| Sidecars observed at these reads | 0 |
| Main bytes and file/directory identity changed by investigation | false |

Event keys match the two audit import targets internally, but the completed
import batches and source are absent. IDs and file digests are not published.
No sidecar now does not exclude earlier unlinked files. This establishes
persisted inconsistency, not a cause in FTS, SQLite, cleanup or filesystem.

New independent controls used the unchanged fixed 10k catalog:

| New synthetic control | Pages / freelist | Change counter / schema cookie | Event / audit / FK |
| --- | ---: | ---: | ---: |
| Fresh migration only | 36 / 0 | 1 / 24 | 0 / 0 / 0 |
| Fixed 10k import plus reimport | 2,172 / 17 | 3 / 24 | 2 / 2 / 0 |
| Core-row DELETE with FK off in the disposable control only | 2,172 / 1,319 | 4 / 24 | 2 / 2 / 2 |
| VACUUM of that disposable control | 850 / 0 | 5 / 25 | 2 / 2 / 2 |
| Raw SQLite backup of that control to a new path | 850 / 0 | 1 / 1 | 2 / 2 / 2 |

The latter control retained 944 FTS data rows / 3,270,666 bytes and 259 index
rows despite zero visible FTS rows. The anomaly instead resembles fresh
schema/FTS storage plus orphaned import records. **Inference:** ordinary DELETE,
that DELETE+VACUUM sequence, or a pure search-result error alone does not explain
all differences. Partial state reset is a candidate description, not a proven
replacement or attributed cause.

Function-scoped fixtures, explicit API DB paths, source/destination separation
and restored monkeypatch scopes were reviewed. No matching DELETE/VACUUM or
inverted-copy route was found. Historical per-operation file identities,
connection trace and exact failing collection order are missing, so present-day
successful comparisons cannot close the issue.

## Independent reproductions and corrections

| Work | Evidence / correction | Additive tests |
| --- | --- | ---: |
| P0-B DB boundaries | 32 pre-correction failures across corrupt references, replacement/unknown identities, cleanup and inspection limits; snapshot guard, existing-file opens and readonly native FTS inspection | [39](db-guard-forensics.md) |
| P1 native qualification | 8 existing observer/classification defects plus newly specified per-mode gates; thread/lifetime/close/runtime checks and separate direct-backup capture | [40](native-qualification-forensics.md) |
| P2 ZIP boundaries | 24 FAIL / 16 valid controls before correction; bounded complete-stream/size/CRC/header checks and dictionary limit | [40](input-boundary-forensics.md) |
| P3 acceptance | 12 FAIL / 8 PASS before correction; strict offline bool, cancelled-attempt review, private repr omission and fixed transport diagnostics | [20](acceptance-forensics.md) |
| P0-A diagnostic harness | Sequential finite scopes and strict count-only evidence; pytest link-alias ambiguity reproduced and corrected in the new harness only | [42](data-forensics-harness.md) |

Total: **181 additive tests**. These refuse independently reproducible unsafe
states; they are not regression evidence for the historical root cause.
Original migrations, fixtures, search expectations, timeouts, platform skips,
DOM/E2E assertions and UI files are unchanged. CI pytest basetemp is now a new
checkout-local run/attempt path. One bounded observed fixed-10k child runs
sequentially after each matrix suite. No CI job/timeout/artifact allowlist is
removed or broadened.

## Bounded comparisons

Local conditions: Linux x86_64, Python3.12.14, builtin SQLite3.53.1; start source
above with reviewed uncommitted additions. Every child has a new ignored root,
process-local TEMP and finite timeout. The seven-module related selection is
**not** the reconstructed historical 122-pass collection order.

| Current comparison | Observed | Unobserved |
| --- | --- | --- |
| Original single gate | 1 PASS | 1 PASS |
| Related seven modules | 89 PASS / 1 platform SKIP | 89 PASS / 1 platform SKIP |
| Complete current suite | 878 PASS / 3 platform SKIP | 878 PASS / 3 platform SKIP |

Each observed scope recorded 116 connections / 809 checkpoints, expected final
1 source / 100 conversations / 10,000 messages and FTS rows / 2 imports, events
and audits / FK0, retained identity, equal committed-close/reopened counts,
prepared core DELETE/DROP0 and observation errors0. Unobserved single/related
also retained those final counts after correcting the new diagnostic's pytest
link-alias discovery defect. The observer changes timing; neither mode excludes
an intermittent historical failure. See [bounded harness](data-forensics-harness.md).

## Runtime/storage surfaces remain separate

| Layer/surface | Evidence | Unqualified scope |
| --- | --- | --- |
| SQL logical | Original UNIQUE/CHECK/trigger partial rollback, TEMP/sort, FK/FTS/hash, backup/restore | Power loss and historical 10k cause |
| Native VFS | Actual Python3.12.3/SQLite3.45.1 at 2,048 rows: errors/outside/default changes0; WAL FILE2 subjournal opens / 1,968 requested writes / 4,157,400 bytes, MEMORY0 | DELETE NOT RUN, positive control did not spill; builtin3.53.1 exports unavailable |
| Direct backup experiment | Two main opens/closes per mode, READONLY1/READWRITE1, logical equality | Production backup API uncaptured; readonly main does not qualify WAL/SHM |
| Named DB/journal/WAL | Private sibling/link checks and cooperative main/parent identity checks | Atomic same-user/admin races, inode reuse and ABA replacement |
| Multipart | Memory-only 8 MiB file / 15s body / two active imports | Total RSS, forced OOM and owner browser |
| OS unnamed TEMP, SHM/mmap, unlink, crash, swap/pagefile | No physical capture or encryption qualification | NOT RUN / BLOCKED for private data |
| Owner Windows ACL/offline/browser/other user | No owner evidence | NOT RUN; runner evidence cannot substitute |

FILE control must open **and write** a statement journal in the same mode before
MEMORY zero earns that workload's synthetic PASS. Generic capture is separate.
Runtime mismatch, callback failure, timeout/crash are FAIL, never unavailable.
No default VFS, unsafe journal/synchronous option, system TEMP, OS ACL or kernel
setting changed. [Native scope](native-qualification-forensics.md) distinguishes
the direct-backup experiment from production copy connections.

## Opt-in performance observation

One fresh-root benchmark sampled each operation once: existing 250-message/
conversation fixture, 100-result page, Linux x86_64, CPython3.12.14,
SQLite3.53.1, nine reported logical CPUs, wall-clock perf_counter and tracemalloc
Python allocations only; concurrent Work activity possible. Start-source
working tree, no full RSS/swap/native allocation or invented performance target.

| Messages | Import seconds | Japanese search ms | Reimport inserted / duplicates | Tracked peak bytes |
| --- | ---: | ---: | ---: | ---: |
| 1,000 | 0.156008 | 30.409 | 0 / 1,000 | 813,473 |
| 10,000 | 1.616099 | 77.338 | 0 / 10,000 | 7,466,316 |
| 50,000 | 9.129473 | 440.325 | 0 / 50,000 | 37,376,332 |

All stages preserved Japanese/literal-percent totals, unique-term1, final empty
page, DB/FK/FTS/hash integrity and nine active logical tables after copy/restore
to a new path. 50k stage total33.610863s, backup5.478592s. Measurements do not
resolve the fixed10k failure or qualify owner-machine performance.

## UI, public evidence and remaining gates

White N, off-white/pale-blue background, thin halo/ring and six navigation stars
are retained with **zero frontend source/test changes**. Local DOM47 and
TypeScript/Vite passed. Start-source desktop/mobile images were viewed; final
Chromium7, five widths and four synthetic PNGs require new source CI. Whole-image
pixel equality is not inferred from unchanged source; timestamps may differ.

Only four existing synthetic PNGs and two Windows runner report archives are
allowed, one-day retention. Native/forensic reports, DBs, journals, raw traces
and fixtures remain local/ignored. Inspect final member allowlists, digests and
redacted report fields before citing artifacts.

Consumer ChatGPT/Claude real adapters remain disabled/BLOCKED without approved
anonymized samples. Owner Windows manual gates remain NOT RUN. Six connectors
are disconnected/execution-disabled, zero provider calls/cost; V2–V5 LOCKED.
Encryption, deletion and dispatch are not enabled. Next priority: retained
anomaly provenance and reproducible identity/transaction evidence, then physical
storage qualification. Owner minimum: separately reviewed redacted report plus
manual gate results; provider samples require separate approval/private
acceptance. Do not send raw DB/key/export/console data.

## Primary references

- [SQLite temporary files and statement journals](https://www.sqlite.org/tempfiles.html)
- [SQLite auto_vacuum and foreign_key_check](https://www.sqlite.org/pragma.html)
- [FTS5 integrity command](https://www.sqlite.org/fts5.html#the_integrity_check_command)

These describe interfaces and limits; they do not establish this anomaly's cause.
