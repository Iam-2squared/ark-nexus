# SQLite statement journal evidence — bounded synthetic scope

2026-10-12 NEXT batch. Official V1 remains **BLOCKED**, and private imports
remain forbidden. Successful rollback, `temp_store=MEMORY`, a VFS count of zero,
or an empty directory is not a general physical-storage qualification.

## Reproducible SQL and native probe

From the reviewed Nexus checkout, with its development dependencies installed:

    python -m nexus.sqlite_probe --rows 2048

The default creates a NEW `tmp/sqlite-evidence/<random-id>`; an optional `--root`
must be a new literal checkout-local directory beneath `tmp`. Existing paths,
links/junctions, outside roots, invalid source revisions and unbounded row counts
are refused. No owner database/key/export is accepted. The operation retains its
own synthetic files; it never cleans OS TEMP or an existing profile. `report.json`
is local; it is **not added to the CI artifact allowlist**. CI prints only the
sanitized classification/count report, with PR source HEAD and checkout HEAD
separate. A PR merge checkout SHA is not the source SHA.

The SQL workload uses the actual Nexus migrations, synthetic Store import, FTS
triggers, integrity checks, and safe backup/copy code. For DELETE and WAL on new
databases it tests three late-failing statements inside BEGIN:

| Case | Partial work before failure | Required result |
| --- | --- | --- |
| Multirow INSERT, late UNIQUE collision | 2,047 successful insert callbacks | The failed statement adds zero rows; earlier project insert in the same transaction remains |
| Multirow UPDATE, late CHECK violation | 2,047 successful update callbacks | Payload/amount changes all roll back; prior transaction write remains |
| Message content/hash UPDATE, late trigger RAISE(ABORT) | 2,047 successful update callbacks, with real FTS update triggers | Message/hash/FTS changes all roll back; prior write and source provenance remain |

Each case compares all 13 logical workload tables internally before/after the
failed statement, checks SQLite/FK/FTS/hash integrity, then commits the earlier
write. FTS5 internal integrity and original/changed-token MATCH counts are checked
as well as logical FTS rows. Digests/rows/IDs are never output. Progress-handler interruption is a
separate test: explicit rollback must restore the entire preceding snapshot.
TEMP table / DISTINCT / sort is also exercised. New backup and new restore must
match the post-commit logical snapshot, MATCH results and stored integrity.

Bounds are 32..8,192 rows, 2 MiB maximum SQLite value, 16 cache pages, at most
128 MiB of database pages (page limit calculated from the actual page size),
20 seconds of SQL progress budget per mode, and a 60-second
native child deadline. These bound the synthetic workload, not all server RSS or
physical memory. No real OOM, power loss, privileged tracing or secure erasure is
claimed. Forced termination can leave the new private synthetic files behind.

## Native binding and positive control

`_sqlite_vfs_probe` is used only in a disposable subprocess; the API never imports
or registers it. It obtains exports from the Python extension's dependencies,
the already loaded Windows `sqlite3.dll`, or builtin executable exports. It does
not search/load an independent system SQLite. Version and source ID must match
Python, and an explicit `sqlite3.connect(...?vfs=...)` must reach the observer.

Registration uses `makeDflt=0`. The original VFS and native files are unmodified;
a wrapper file forwards all supported IO methods to its separate original file.
Default VFS identity is checked before/after registration and unregistration.
The capture counts `xOpen`, `xWrite` calls/bytes, `xClose`, `xDelete`, and SHM
callbacks. Named paths outside the new root fail closed. No buffers, names,
absolute paths, source IDs or raw traces are serialized. Parent TEMP variables
stay unchanged. Four TEMP variables are set only in the new child before imports.

A **test-only FILE positive control** repeats the same workloads on additional
new databases, without changing Store/backup or production settings. This shows
whether the instrumentation can actually observe a spilled subjournal. A build
compiled with TEMP_STORE=3 reports that control NOT RUN rather than pretending to
switch it. OFF/MEMORY journal modes and synchronous=OFF are never used.

| Local interpreter used to execute Nexus code | SQLite | Native result | Measured scope |
| --- | --- | --- | --- |
| Work default Python 3.12.14, builtin `_sqlite3` | 3.53.1, TEMP_STORE=1 | NOT RUN / capability_unavailable, registrations0 | SQL workload PASS; no exported VFS symbols; no native placement claim |
| Separate installed Python 3.12.3, dynamic `_sqlite3` | 3.45.1, TEMP_STORE=1 | VFS synthetic PASS, captured=true | Actual Python connection reached observer; named outside0, callback errors0, default VFS unchanged |

The second interpreter loaded **Nexus code** with its own Python SQLite module.
It is a separately labelled runtime, not evidence qualifying the Work default
builtin 3.53.1 or any owner's runtime. No alternate SQLite library was supplied
to either interpreter. In the 2,048-row observed run, FILE/WAL opened **2 unnamed
statement journals**, with **1,968 xWrite calls / 4,157,400 requested write bytes**.
The MEMORY workload had zero statement-journal VFS opens for these exact cases.
Both configurations preserved rollback/integrity/backup equality. The control
also opened 2 unnamed transient databases; 4 unnamed opens total. These are VFS
calls, not fsync durability, syscall capture or secure deletion evidence.

Latest Linux/Windows x Python3.12/3.13 native classifications must come from the
new source-HEAD CI logs. An unavailable capability is `captured=false`,
`reason=capability_unavailable`, **NOT RUN**. Native callback errors, subprocess
crash/timeout, scope escape or incorrect SQL results fail the additive CI step;
they are not recategorized as missing capability.

## Storage-surface gates

| Surface | Current evidence | Remaining gate |
| --- | --- | --- |
| Multipart upload staging | Bounded BytesIO; no spool factory, original and additive cancellation/framing tests | Owner Windows/browser/offline NOT RUN |
| SQLite TEMP table/sort/materialization | Per-connection MEMORY, real SQL; bounded VFS scope on the labelled runtime | Actual owner build and OS-level qualification NOT RUN |
| Statement journal | Late UNIQUE/CHECK/trigger rollback; FILE positive-control xOpen/xWrite; MEMORY observations per runtime | All-path/unnamed physical location and owner runtime still BLOCKED |
| Main rollback journal | Named sibling VFS opens/writes in DELETE; existing private-path guards | Owner ACL, crash/power-loss remnants NOT RUN |
| WAL / SHM | WAL VFS writes and SHM method calls, logical rollback and backup equality | SHM may be handled inside native VFS; its physical syscalls/mmap are not captured |
| Backup / restore | New-path logical 13-table equality, FK/FTS/hash checks | Backup connections not in VFS capture; owner ACL/encryption NOT RUN |
| Crash / OS caches / unlink remnants | Only cooperative close/cancellation observed | Power loss, real OOM, snapshots and remanence NOT RUN |
| RAM / swap / pagefile / crash dumps | No protection/erasure qualification | BLOCKED for private data |
| Normal Windows profile ACL / other OS user / offline UI | No owner evidence | NOT RUN; runner success is not owner PASS |

The observer sees unnamed `xOpen(NULL, ...)` before the native VFS chooses a
physical pathname, including files it may unlink immediately. Therefore its
counts **cannot locate those physical files**. Child-local TEMP settings reduce
test exposure but are not independently verified physical containment. No
unverified global `sqlite3_temp_directory`, kernel hook or OS setting is changed.

The parent's evidence boundary checks exact recursive schemas, fixed strings,
strict boolean/integer counts and duplicate keys before forwarding child JSON.
Four mocked-child failures preceded this correction; unknown/private fields,
contradictory duplicate keys and missing capture schemas reject with a fixed
diagnostic. No raw child output is logged on rejection.

## Primary references

- [SQLite temporary files / statement journals / locations](https://www.sqlite.org/tempfiles.html)
- [temp_store and compile-time interaction](https://www.sqlite.org/pragma.html#pragma_temp_store)
- [VFS object and xOpen contract](https://www.sqlite.org/c3ref/vfs.html)
- [sqlite3_io_methods ABI](https://www.sqlite.org/c3ref/io_methods.html)
- [VFS registration and default selection](https://www.sqlite.org/c3ref/vfs_find.html)

These describe interfaces and risks. They do not replace per-runtime observations
or owner evidence. V1 remains BLOCKED; V2–V5 remain LOCKED.
