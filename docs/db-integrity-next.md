# Additive stored-record integrity checks — 2026-10-12

This batch uses only fresh synthetic databases beneath the Nexus checkout's
ignored `tmp` directory. No owner profile, key, export, existing backup, migration
or OS permission was changed. The tests are additive to the original 1,000-record
reimport, fixed 30 + 30 searches, 10,000-record pagination and 5,000-record
concurrent-import gates.

## Reproductions and corrections

`tests/test_next_database_integrity.py` initially produced **14 FAIL / 1 PASS**
on the working tree based on source
`79e56eb20a581825b0ce2392c82fc0d7127918fa`, before correcting `integrity.py`:

| Synthetic condition | Before | Corrected behavior |
| --- | --- | --- |
| NULL, empty, NUL-containing or BLOB primary key in an unreferenced source, project or proposed task; 12 cases | SQLite and FK checks returned zero errors; overall integrity incorrectly passed | Count `invalid_primary_keys`; refuse copying the invalid source |
| BLOB message content, including invalid UTF-8 bytes; 2 cases | Hash inspection raised `AttributeError` instead of returning a report | Count one content-hash mismatch without converting bytes into history text |
| BLOB digest containing the bytes of a valid SHA-256 string; 1 case | Already rejected | Remains rejected; a digest must remain text |

The primary-key check covers the ten existing logical tables whose identity is
a TEXT primary key, including the `sync_cursors.source_id` identity. It reads and
counts invalid stored values; it does not repair data, introduce a new migration
or enable the reserved task/connector tables. Hash inspection reports counts and
does not put record content or identifiers into the response.

Four additional interruption cases exercise `KeyboardInterrupt` and `SystemExit`
after the writer closes, with either a newly substituted file or a hard-linked
synthetic sentinel at the destination. The existing copy cleanup preserves a
replacement with a different file identity, closes both connections, and leaves
the source unchanged. This is a controlled synthetic guard test, not protection
against privileged or same-user filesystem races.

One backup/restore test fills the reserved task, evidence and cursor tables with
synthetic inactive records and compares all **12 logical tables** at a new backup
and a second new restore path. The restored source still reports no external
provider connection and no dispatch capability. No task is executed.

The completed additive module has **20 tests**. Linux working-tree verification
is synthetic only; Windows/Python compatibility and final source-HEAD CI are
reported separately in the batch evidence. Owner Windows gates remain NOT RUN.

## Bounded 10,000-record observation

Three independent fresh-root runs used the existing benchmark on Linux x86_64,
CPython **3.12.14**, SQLite **3.53.1**, nine reported logical CPUs, and
`tracemalloc` for Python allocations. Each operation was sampled once per root,
with 250 messages per conversation and a 100-item search page. Full process RSS,
pagefile/swap, filesystem-native writes and owner-machine performance were not
measured. Concurrent Work activity may affect wall time.

| Fresh-root run | Import seconds | Japanese search milliseconds | Tracked Python peak bytes | Reimport inserted / duplicates |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.086984 | 48.894 | 7,470,068 | 0 / 10,000 |
| 2 | 1.306966 | 49.464 | 7,462,412 | 0 / 10,000 |
| 3 | 1.128787 | 45.637 | 7,465,524 | 0 / 10,000 |

Each run found 10,000 Japanese/literal-percent hits and one unique-term hit,
verified the empty page at offset 10,000, passed stored-record integrity, and
matched the nine active logical tables used by the existing benchmark after
copy-to-new-path restore. Their sanitized `report.json` files remain local and
are not CI artifacts. These times are observations, not retroactive PASS targets.

The previous single 10,000-record search anomaly did not recur in these three
benchmark runs, but **did recur once in the frozen regression suite** in this
batch. Its cause remains **unresolved**; this batch does not label it fixed.

## Unresolved frozen-suite observation

One Linux/SQLite 3.53.1 related-suite run ended with **122 PASS / 1 FAIL /
1 platform SKIP**. All 20 new tests passed; the unchanged
`test_10000_message_reimport_and_complete_pagination` returned a Japanese search
total of zero after earlier overview, integrity and conversation-page checks had
passed. The failed synthetic DB was retained for read-only investigation.

| Subsequent read-only observation | Value |
| --- | ---: |
| Main file size / pages | 147,456 bytes / 36 |
| Source / conversation / message / import-batch / FTS rows | 0 / 0 / 0 / 0 / 0 |
| Source-event / audit rows | 2 / 2 |
| SQLite integrity errors / FK errors | 0 / 2 |
| Repeated exact joined-search count | 0 on all 10 queries |

The same on-disk counts were independently read with system Python 3.12.3 and
SQLite 3.45.1. This is a separate runtime used only to inspect the retained file;
it does not qualify the Nexus runtime's native storage behavior. The evidence
shows a persisted logical-state discrepancy and does not establish a cause in
the FTS optimizer, application, SQLite build or filesystem.

A fresh-root run of the original 10,000-record test alone passed and retained
10,000 messages/FTS rows with zero FK errors after process exit. A separate
20-new-test-plus-original-test sequence, using additional read-only count
observations at commit and close, passed **21 tests**. Its 116 observed
connections showed the expected 10,000-message state before/after import commits
and no close-versus-reopened-disk count discrepancy. These successful runs do
not negate the retained failure. No gate, fixture, search expectation, timeout or
index was weakened or rebuilt to hide it.

The unchanged complete related suite was then rechecked in another fresh root:
**123 PASS / 1 platform SKIP**, in 16.14 seconds. This validates the 20 additive
checks alongside the existing frozen cases at that working tree; it does not
establish that the intermittent discrepancy has been corrected.

None of these logical checks qualifies SQLite statement-journal native storage,
crash remnants, swap/pagefile exposure, normal Windows profile ACLs or real
provider-format completeness. Those gates remain separately reported and V1
official remains BLOCKED.
