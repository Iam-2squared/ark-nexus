# Stored-record refusal and identity guards — 2026-10-12

This work starts from source `18e61002a7f89bc065c296e100a574bf10ff1ac4`.
All reproductions use newly generated synthetic databases beneath this checkout's
ignored `tmp`. The retained 10,000-message failure evidence was not used as a
write target, repaired, regenerated or deleted. These protections **do not identify
or fix the intermittent 10k disappearance**. Official V1 remains **BLOCKED**.

## Reproduction first

The initial 28-test module `tests/test_forensic_database_guards.py` returned
**26 FAIL / 2 PASS** before the corrections. A further destination-sharing
reproduction failed separately before its cleanup correction. Five later
reproductions covered initially unavailable file identities (two cases),
oversized stored FTS values, the copy-byte budget and the inspection deadline.
They failed before their corresponding correction. **32 failure cases** were
observed across these reproducible conditions; this is not a count of distinct
root causes or a claim to have explained the retained 10k anomaly.

| Synthetic condition | Before | Corrected boundary |
| --- | --- | --- |
| Two messages reference an absent conversation; 12 API read/write operations | Successful 200/201 responses; import could write another receipt | Fixed 503 `Local storage unavailable`, no new logical records |
| Missing/mismatched import event or audit, NULL batch source or incomplete receipt; 8 cases | Overall integrity incorrectly passed | Count the known import-provenance defect; refuse reads, writes and backup |
| Logical message/hash/FTS content agrees but native postings still describe the previous text | Logical FTS checks did not expose index disagreement | `fts_index_errors=1`; refuse backup without rebuilding the source index |
| A regular database substitutes the main path between operations; 3 cases | Store accepted the substituted file | Bind Store to the initial main-file and directory identities |
| Bound main file disappears | SQLite recreated an empty file | Existing-file URI `mode=rw`; refuse without creating a replacement |
| Backup source substituted after opening | Copy could succeed for the wrong source | Source and destination identity checkpoints before and after copying |
| Interrupted new destination acquires another hardlink | Cleanup removed the original destination name | Preserve a changed, linked or differently parented destination |
| File or directory identity initially unavailable | A zero identifier could be accepted as the binding | Refuse unknown identities with a fixed path-free error |
| Oversized FTS BLOB, copy-budget exhaustion, expired inspection clock | Diagnostic could allocate/copy before checking a finite resource budget | Native length checks precede Python fetch; fixed refusal on budget/deadline failure |

The two original passing cases already rolled back injected commit failure or
`KeyboardInterrupt`, closed the connection, preserved receipt/FTS/provenance
counts and allowed an explicit idempotent retry. Those conditions remain tests.

Five additional regression checks cover main-file preservation with a changed
parent directory, one WAL snapshot for reference approval plus result retrieval,
effective FK enforcement before yielding a connection, a read-only authorizer
with zero source write authorizations, and no deep FTS/hash scan on page requests.
The additive module contains **39 tests**. No frozen fixture, migration, expected
search result, timeout or platform gate was weakened.

## Public operations and diagnostics

Public Store reads open `BEGIN`, validate foreign keys and known import-provenance
references, then retrieve their result within that snapshot. Message existence,
total and rows now use one snapshot as well. Import and project writes begin
`BEGIN IMMEDIATE` before validation. Import checks the completed receipt, event
and audit relation again before commit. There is no hidden retry, repair,
successful empty fallback or automatic database recreation.

The existing `/api/v1/integrity` remains available for counts-only diagnostics
when logical data is corrupt. It reads the same snapshot and reports independent
FK, primary-key, import-provenance, logical FTS, content-hash and internal FTS
checks. `coverage=stored_records_only` and
`provider_completeness_verified=false` remain unchanged. Physical damage or an
unavailable storage capability can still return the fixed generic 503.

The import-specific checks deliberately validate only the implemented
`import.completed` and successful `import` audit relation. They do not invent
semantics for future provider events, task/evidence targets or connector tables,
and do not enable any reserved execution table. They detect known incomplete,
missing and dangling import provenance without adding a migration.

The lightweight page guard does **not** hash every message or clone the FTS index.
It is not a complete stored-record validation and cannot certify provider
completeness or rule out all corruption. Explicit deep integrity and offline
copy inspect the additional surfaces. Corruption must be investigated and
recovered separately; the code does not reinterpret missing records as deletion.

## Native FTS integrity on a nonpersistent inspection copy

[SQLite's FTS5 integrity-check command](https://www.sqlite.org/fts5.html#the_integrity_check_command)
compares index structure and content. Executing that special INSERT against a
healthy source opened with `mode=ro` returned `SQLITE_READONLY` in the tested
runtime. It is therefore not used as a source write or repair operation.

The explicit inspection instead copies the five existing FTS5 shadow tables
(`data`, `idx`, `docsize`, `content`, `config`) from the caller's snapshot into a
new `sqlite3.Connection(':memory:')` in the **same Python runtime**. It verifies
memory TEMP there, runs the native integrity command on that inspection copy,
then closes the memory connection on success or exception. Native SQL length
checks precede every Python shadow-value fetch. Copied values and scratch pages
are capped at **128 MiB**, a single inspection value at **2 MiB**, and scratch
SQL/copy work at **10 seconds** using a progress handler and elapsed-time
checkpoints. The same single-value cap protects the explicit message-hash scan
from a forged large content/digest BLOB. No existing upload, workload, benchmark
or test timeout was changed.

The scratch deadline cannot preempt a blocked OS read or a single source SQL
operation: the caller's existing source progress handler is left unchanged.
Python/native overhead, RSS and pagefile use are not bounded or qualified by the
copied-value/page budget. A large legitimate index can therefore require a
separately reviewed inspection approach; exceeding this diagnostic limit is a
failure, not a successful partial report or automatic repair.

It does not load an
alternate SQLite library, rebuild any source index, modify a global VFS or
change source journaling settings. The source-authorizer test rejects all source
INSERT/UPDATE/DELETE/DDL and confirms zero changes and unchanged main-file bytes.

Only native corruption codes become the anonymous `fts_index_errors` count.
Unexpected failures remain failures and are handled by the existing fixed API
or CLI diagnostic. The copy checks a stable, committed snapshot; it does not
qualify a writer's unflushed native FTS cache, OS storage paths or crash behavior.
Inspection memory still depends on the stored FTS index within those copy limits. Full process RSS,
swap/pagefile exposure and secure erasure are not measured or protected.

## Filesystem and cleanup limits

Store records `(device, file identity)` for both its main file and immediate
private directory. Portable path, symlink/junction/reparse/hardlink, POSIX mode
and SQLite sidecar checks still run at connection checkpoints. The bound main
identity is checked before/after opening and around commit; SQLite opens an
already-created file with `mode=rw`. Sidecar identities are not permanently
pinned because SQLite legitimately creates and removes journals/WAL/SHM.

Backup binds its current source and exclusively created destination identities,
uses a read-only source snapshot, and opens the destination with `mode=rw`.
On failure it removes only that invocation's still-private, unchanged new file
under the unchanged parent. Replaced files, linked destinations and changed
parents remain. Cleanup failure preserves the original error and can leave a
new partial file for separate investigation. Existing backups or evidence are
never overwritten or automatically deleted.

These are checkpoint checks, **not atomic protection against hostile same-user
or privileged races**. Python's connection does not expose a verified SQLite
file descriptor; inode/file-ID reuse or an ABA replacement can escape a simple
identity comparison. Windows normal-profile ACLs, native physical paths,
unlink/crash remnants, backup encryption and owner isolation remain unqualified.

## Local evidence and performance conditions

Working-tree verification on Linux/Python **3.12.14**/SQLite **3.53.1**:

| Suite | Result | Seconds |
| --- | --- | ---: |
| Initial reproductions before correction | 26 FAIL / 2 PASS | 2.57 |
| Initial guards plus prior integrity/path/TEMP tests | 79 PASS | 3.47 |
| Frozen 10k/5k concurrency, migration, integrity, data, SQL probe and benchmark | 100 PASS / 1 existing platform SKIP | 20.38 |
| Final 34 guards plus prior integrity/path/10k/backup regressions | 87 PASS | 18.68 |
| Final 39 guards plus prior identity/TEMP/SQL probe/benchmark regressions | 138 PASS | 10.40 |
| Ruff on the four changed modules and new tests | PASS | — |

A separate new 10,000-message synthetic root measured only the reference guard
20 times after the resource limits: median **5.478 ms**, maximum **8.739 ms**.
One explicit deep integrity call, including the bounded memory inspection copy,
took **422.996 ms** and returned OK.
These were wall-clock observations during concurrent Work activity, not fixed
PASS targets or before/after throughput comparisons. RSS, hardware isolation and
owner-machine performance were not measured. The original 1k/10k/50k benchmark
definitions were not changed. Exact final source-HEAD CI results are recorded in
the batch report separately; local success is not Windows owner evidence.

The earlier intermittent 10k state discrepancy remains **OPEN/BLOCKED** until
its cause and independent regression evidence are established. Consumer real
formats remain disabled/BLOCKED, owner Windows gates NOT RUN, and V2–V5 LOCKED.
