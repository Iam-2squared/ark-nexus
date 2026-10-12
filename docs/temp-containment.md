# Temporary storage containment — synthetic verification only

2026-10-12. Private exports remain forbidden; official V1 remains BLOCKED. This
distinguishes implemented controls from remaining storage/owner Gates.

## Implemented controls

- `LocalBoundary` checks auth/Host/Origin/CSRF and framing before receiving input.
  Limits: ordinary64 KiB, import8 MiB+64 KiB envelope, 15 seconds for the complete
  body. Per application process at most two import requests receive/parse/store
  concurrently. A third gets fixed429 before body reads; retry is explicit.
- `MemoryImportRoute` retains File/Form validation but supplies `MemoryMultipart`.
  One file and the four known fields only; duplicate/unknown fields, ambiguous
  headers, invalid UTF-8, incomplete boundaries, excessive headers/fields and
  files over8 MiB reject before writes. A bounded BytesIO entirely replaces
  disk-capable spooling. No tempfile factory, rollover, file descriptor, global
  TEMP variable or `tempfile.tempdir` mutation is used in production.
- Owned buffers close synchronously in finally on invalid forms, exceptions,
  cancellation, KeyboardInterrupt and SystemExit. This frees buffers, not every
  copy in RAM/swap/dumps, and is not secure erasure.
- Each Store and backup/restore connection checks compiled TEMP_STORE is1/2/3,
  sets temp_store=MEMORY and reads back2 before SQL. Disk-only/unknown builds
  fail closed with path-free diagnostics. No global temp_store_directory change.
- DB/journal/WAL/SHM retain path/link and owner-only POSIX checks. Backup uses a
  new destination only; interruptions close both connections and remove only the
  newly created destination with matching identity. Existing sidecars remain.

## Reproduction and platform evidence

`test_temp_containment.py` initially gave17 FAIL/1 PASS. It simulates common TEMP
inside the checkout with synthetic markers only, including >1 MiB valid/invalid
uploads and dry-run. After changes: zero spool/tempfile calls; temp environment
unchanged; accepted uploads work when common-temp allocation raises ENOSPC,
EROFS or EACCES. OS common TEMP is not scanned, cleaned or changed.

The lifecycle suite tests deadlines, capacity/release, partial streams and
interruption cleanup. Every Windows/Linux Python3.12/3.13 job runs these additive
cases. The actual SQLite TEMP table/sort test reads back2 and an unnamed TEMP
database. This verifies those operations/configuration on the runner build, not
exhaustive native file-open observation or owner Windows evidence.

## Remaining gates

| Surface | Classification | Remaining evidence |
|---|---|---|
| Multipart spool | Implemented memory-only, synthetic-tested | Owner Windows/browser/offline |
| SQLite TEMP/sort/materialization | MEMORY enforced on verified build | Native per-platform observation and owner runtime |
| SQLite statement journals | Bounded SQL and native VFS observation added | MEMORY alone does not establish all-path placement; see [runtime-specific statement evidence](sqlite-statement-observation.md) |
| Journal/WAL/SHM/crash leftovers | Private sibling checks/recovery regressions | Normal Windows profile ACL and owner crash/remnant checks |
| RAM/swap/pagefile/crash dumps/OS snapshots | Not encrypted or erased | Separate threat model and owner-approved protection |
| Same OS user/admin/SYSTEM/path races | Outside isolation guarantee | OS account separation and normal-profile Gate |

Linux strace was refused by the sandbox's ptrace restriction. The Work default
builtin _sqlite3/SQLite3.53.1 has no exported VFS symbols: its native capture
remains NOT RUN. The NEXT batch adds an explicit-VFS disposable-process harness
and observes a separately labelled Python3.12.3/SQLite3.45.1 actually executing
Nexus code, including a FILE positive control with2 spilled statement journals.
No OS settings, original VFS or default VFS changed. The [detailed scope matrix](
sqlite-statement-observation.md) separates VFS calls from physical unnamed
pathnames, syscalls, owner runtime, crash and swap. An empty directory after a
query does not prove absence of an unlinked temporary file.

Two import permits bound concurrent requests, not total RSS/SQLite allocation or
all server connections. Normalization/decompression need additional RAM; forced
termination/OOM cannot guarantee cleanup. Original32 MiB ZIP expansion/50,000
messages/compression-ratio limits remain. Private imports stay forbidden until
statement journals, normal-profile ACL and owner evidence are resolved.

## Primary sources

- [SQLite TEMP_STORE/build interaction](https://www.sqlite.org/pragma.html#pragma_temp_store)
- [SQLite temporary surfaces and OS locations](https://www.sqlite.org/tempfiles.html)

The documented pragma does not qualify statement journals. Runtime observation
and future containment must cover them before claiming private storage safety.
