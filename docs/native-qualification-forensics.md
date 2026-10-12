# Native SQLite qualification — count-only forensic follow-up

Repository: **Iam-2squared/ark-nexus** only. This additive work preserves the
three original late-failing SQL cases, row/cache/page/time limits, source versus
merge-checkout distinction, public artifact allowlist and existing CI jobs.
Official V1 remains **BLOCKED**; private imports remain forbidden.

## VFS capture and statement-journal qualification are separate

`native.status=synthetic_PASS` means the actual Python runtime reached the
explicit disposable VFS, the SQL workload was correct, named opens stayed within
the new root, and no callback/default-VFS error occurred. It is not a general
statement-journal placement claim. `statement_journal_gates` now gives separate
DELETE and WAL results derived from the same-mode counters:

| Observed condition | Statement-journal result |
| --- | --- |
| FILE control has positive subjournal open, requested write-call and byte counts; MEMORY has zero | Bounded `synthetic_PASS` for that mode/workload |
| FILE control does not open and write a subjournal | `NOT RUN / positive_control_not_observed` |
| TEMP_STORE=3 prevents the FILE control | `NOT RUN / compiled_memory_only` |
| MEMORY opens or writes a subjournal | `BLOCKED / memory_subjournal_observed` |

A FILE/WAL control never qualifies DELETE. A small workload may produce a valid
generic VFS capture while both statement-journal gates remain NOT RUN. All these
gates retain `storage_location_qualified=false` and `private_import_allowed=false`.
The strict parent JSON boundary independently derives each gate from the counts;
unknown fields, changed classifications, coerced counts or private text reject.

## Disposable observer error and lifetime boundaries

The observer is deliberately single-threaded, matching the reviewed synthetic
child. Open/delete/IO/registration operations from a different thread refuse
before forwarding to native IO. This is not a concurrency-capable general VFS.
Each retained file callback verifies the expected live outer file; calls after
close fail rather than forwarding to the old underlying file address. Callback
objects and proxy method tables remain referenced until unregister.

A failed native xClose is now counted as a capture failure even when SQLite
releases the file. A failed xOpen with a valid methods table still forwards its
required close. Unsupported future IO-method versions refuse the proxy and
close the known xClose prefix. Runtime version/source-ID mismatch and an existing
observer registration name are failures, not missing capabilities. Genuine
missing exports/unsupported VFS layout remain NOT RUN. Native crashes, callback
errors, scope escape and timeout still fail the child/CI step with fixed,
content-free diagnostics.

Eight pre-fix regression cases exposed those existing observer/classification
defects. The first 26-case run had 25 FAIL/1 PASS: seven observer defects and
18 newly specified gate contracts failed; a subsequent name-collision case also
failed before correction. These are not 26 independently discovered SQLite data
bugs. The completed additive file has **40 tests**, and the original statement
probe file remains unchanged; together they passed **78 tests** locally. Ruff
passed. Final four-runtime qualification must use the new source-HEAD CI logs.

## Additional observed backup connections

`experimental_backup_capture` adds a separate bounded `Connection.backup`
experiment on the already generated DELETE/WAL sources and new destinations.
It does not alter or replace `maintenance.copy_database`. For each mode the
explicit Python VFS connections must show two main-DB opens/closes, one native
READONLY open, one native READWRITE open and destination writes. Both connections
verify temp_store=MEMORY. A read-only BEGIN fixes the source snapshot; destination
equality covers all 13 workload tables, stored FK/FTS/hash checks, FTS MATCH and
FTS internal integrity. The sources are not updated or regenerated. Backup
progress has a 20-second budget and the native child's existing 60-second bound.

The original `backup_connections_captured=false` still describes the production
copy/restore calls in the original workload. The new experiment explicitly has
`production_backup_api_captured=false`; it proves observation of its direct
backup connections, not production backup storage, OS syscall placement,
interruption durability, encryption or owner ACLs. A failed operation retains
its new synthetic files rather than cleaning any existing profile or OS TEMP.
READONLY here refers to the source SQL connection/main file, not every sidecar:
the observed WAL backup stage also had two native READWRITE WAL opens. No WAL
write callbacks were recorded for that stage; internal SHM/mmap writes are not
captured. A readonly main connection does not qualify all filesystem side effects.

## Local observations, before source-HEAD CI

The reviewed worktree was based on source
`18e61002a7f89bc065c296e100a574bf10ff1ac4`, with these additive files uncommitted
while measuring. Reports and synthetic databases remain in ignored, newly
created checkout-local roots; no database/raw trace becomes a public artifact.

| Interpreter executing Nexus code | Rows | SQL / generic VFS | Statement journal |
| --- | ---: | --- | --- |
| Work Linux Python3.12.14, builtin SQLite3.53.1 | 64 | SQL PASS / native NOT RUN, capability_unavailable | NOT RUN |
| Installed Linux Python3.12.3, its dynamic SQLite3.45.1 | 64 | SQL PASS / actual Python VFS PASS | DELETE and WAL NOT RUN: FILE control did not spill |
| Installed Linux Python3.12.3, its dynamic SQLite3.45.1 | 2,048 | SQL PASS / actual Python VFS PASS | DELETE NOT RUN; WAL FILE2 opens / 1,968 requested writes / 4,157,400 bytes, MEMORY0: bounded WAL PASS |

The installed interpreter uses its own already loaded SQLite dependency, not an
independent library supplied to Work. The 2,048-row direct-backup experiment
observed two main-file opens/closes per mode and preserved logical equality;
native READONLY/READWRITE flags are checked by the final producer and validator.
Callback errors, named outside-root opens and default-VFS changes were zero.
No success for SQLite3.45.1 qualifies Work's builtin3.53.1, another query/runtime,
an owner's Windows machine or a physical pathname chosen after unnamed xOpen.

| Evidence layer | Present scope | Still unqualified |
| --- | --- | --- |
| SQL logical | Original late UNIQUE/CHECK/trigger rollback, interruption, FK/FTS/hash, new backup/restore | Power loss, physical corruption/remanence |
| Native VFS | Mode-specific open/write/close, requested bytes, direct backup connection flags, SHM callbacks | Independent filesystem syscalls, SHM internal file/mmap operations |
| Physical files | Named synthetic paths checked at the observed boundary | Unnamed physical paths, unlink remnants, OS caches, swap/pagefile, crash |
| Owner machine | No owner evidence | Offline/browser/other-user/normal-profile ACL remain NOT RUN |

## Primary interface references

- [SQLite VFS object and xOpen/pMethods contract](https://www.sqlite.org/c3ref/vfs.html)
- [IO methods and failed-open xClose contract](https://www.sqlite.org/c3ref/io_methods.html)
- [Temporary files and statement journals](https://www.sqlite.org/tempfiles.html)
- [Existing bounded observation procedure](sqlite-statement-observation.md)

No default/original VFS callbacks, global temp setting, journal/synchronous
production choice, OS permission or kernel hook is changed. Six external
connectors stay disconnected/disabled; V2–V5 stay LOCKED.
