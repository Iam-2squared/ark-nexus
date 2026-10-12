# Bounded 10k data-forensics comparisons

The [storage NEXT follow-up](storage-next-2026-10-12.md) adds child schema2:
current collection count/digest/anonymous position, nine fixture/test boundaries,
readonly count/header observations, and SQL/context-manager transaction phases.
The historical development tables below are retained, not overwritten with new
measurements. A schema2 comparison also requires complete bound lifecycle
metadata. Old schema1 receipts remain strict/readable; neither format repairs
the historical discrepancy. Unobserved mode adds no boundary file/SQL reads.

The historical 10,000-message persisted-state discrepancy remains **OPEN /
BLOCKED** until its root cause and an independent regression are established.
A successful diagnostic comparison is not a correction. No owner database,
provider export or prior failure evidence is an input to this harness.

`python -m nexus.data_forensics` runs the unchanged
`test_10000_message_reimport_and_complete_pagination` in finite, sequential
pytest subprocesses. Its definition must exactly match the current Git checkout;
the harness hashes that public function internally and records its code digest.
It does not edit the frozen test, fixture, scorer, timeout, migration or index.

| Comparison scope | Child selection |
| --- | --- |
| `single` | Original fixed 10k pytest node only |
| `related` | The 10k module plus next-database-integrity, data-management, integrity, store, fixed-search and concurrency modules |
| `full` | Current complete `tests` directory, including additive checks |

Each scope receives one to three trials. A child has a 10–180 second bound
(default 150); at most nine children run sequentially. This avoids collisions
between full-suite loopback probe fixtures. There is no unbounded random retry,
new provider access or implicit reimport after a failure.

From the Nexus checkout, with development dependencies already installed:

```console
python -m nexus.data_forensics --scopes single related full --trials 1
python -m nexus.data_forensics --scopes single related full --trials 1 --unobserved
```

The default destination is a new UUID directory in ignored
`tmp/data-forensics`. `--root` may specify a **new** directory under this
checkout's `tmp`; existing roots, parent traversal, links, external Git context
and Git alternates are refused. A child has a new pytest basetemp and a new
process-local temp directory; neither parent environment nor OS TEMP is changed.
Automatic root cleanup is deliberately absent. Failed synthetic databases and
count-only evidence remain where that operation created them.

## Observation boundaries

The optional observer is installed only in its dedicated child. It observes the
fixed 10k fixture's main database; unrelated databases and connection factories
explicitly supplied by other tests keep their original factory. Parent
`sqlite3.connect`, connection settings, default VFS, journal mode and production
Nexus code are not patched by this module.

Pytest's `current` link aliases are excluded before any target inspection.
Symlink/junction aliases must not be followed; a zero file identity is refused.
During development, the unobserved locator initially treated a current alias as
a second database and omitted final evidence. A dedicated harness regression
failed before the locator correction. This was a diagnostic discovery defect,
not a cause or correction of the historical 10k persisted-state discrepancy.

Checkpoints record:

- Fixed phase codes at opening, BEGIN, commit, rollback, close, and final review.
- Source, conversation, message, import, FTS, event, audit and migration counts.
- FK-error count, transaction boolean, temp-store integer and journal-mode class.
- Anonymous connection/sequence numbers, internal file-identity equality and
  sidecar-presence booleans. Device/inode values and paths are never emitted.
- DELETE/DROP preparation counts for known main tables. The authorizer always
  returns `SQLITE_OK`; preparation is not proof that the statement executed.

Counts at each checkpoint use one SELECT statement snapshot. An already active
application transaction is observed without changing its transaction boundary.
Independent post-close/final observers use `mode=ro`, `query_only=ON` and a read
transaction. They do not recreate a missing database or repair a damaged one.
The harness does not inspect or publish message bodies, account/source IDs,
SQL parameters, keys, raw pytest traces, or absolute paths.

The report refuses arbitrary child fields/strings, duplicate JSON keys, oversized
evidence, wrong types, child failures, timeout, observer errors and checkpoint
caps. It also requires the frozen test to pass and final counts to retain
1 source, 100 conversations, 10,000 messages/FTS rows and 2 imports/events/audits
with zero FK errors. A committed close-versus-reopen count difference or main
identity change fails the diagnostic comparison even if pytest returned zero.

Observer reads and the connection subclass affect timing and may alter how an
intermittent issue manifests. `--unobserved` provides post-exit readonly counts
without a connection subclass or authorizer. Neither a clean observed nor a
clean unobserved run excludes the retained historical failure. Filesystem
syscalls, crash/swap/pagefile, same-user/privileged races and owner Windows ACLs
are outside this harness's evidence.

`report.json` distinguishes `checkout_head` from an optional independently
checked `--source-head`. On a PR merge checkout without a supplied source SHA,
source is unavailable instead of being inferred from the merge SHA. Working-tree
cleanliness is recorded, so an instrumented development run cannot masquerade
as final source-HEAD CI evidence.

No new CI artifact is added. The synthetic DBs and JSON remain local/ignored;
only reviewed counts, conditions and classifications belong in public evidence.
Owner Windows and real provider-format gates remain NOT RUN/BLOCKED, and V1
official remains BLOCKED regardless of these comparison results.

## Development working-tree observations — 2026-10-12

These finite runs used Linux, CPython 3.12.14 and builtin SQLite 3.53.1, in the
development working tree based on source
`18e61002a7f89bc065c296e100a574bf10ff1ac4`. The report records
`working_tree_clean=false`; these are not final source-HEAD CI results. Each row
used one trial and a distinct new ignored root. Fixture catalog/order came from
the unchanged fixed test; no random fuzzing or seed search was performed.

| Scope | Observer | Pytest PASS / FAIL / platform SKIP | Count checkpoints | Watched connections |
| --- | --- | ---: | ---: | ---: |
| Single | Child connection checkpoints | 1 / 0 / 0 | 809 | 116 |
| Related | Child connection checkpoints | 89 / 0 / 1 | 809 | 116 |
| Full | Child connection checkpoints | 878 / 0 / 3 | 809 | 116 |
| Single | Post-exit readonly only | 1 / 0 / 0 | 1 | 0 |
| Related | Post-exit readonly only | 89 / 0 / 1 | 1 | 0 |
| Full | Post-exit readonly only | 878 / 0 / 3 | 1 | 0 |

All six completed comparisons retained final counts
`source/conversation/message/import/FTS/event/audit = 1/100/10000/2/10000/2/2`,
zero FK errors and unchanged main-file identity. Each observed comparison had
zero DELETE/DROP preparations, zero observer errors and equal committed
close-versus-reopen counts. The related collection is explicitly the seven
modules above, **not a reconstruction of the historical 122-pass collection or
its ordering**. The retained historical failure is still OPEN/BLOCKED.

Two initial unobserved children passed pytest but failed the diagnostic's final
evidence check because of the locator alias defect described above. Their new
synthetic roots were retained. The portable locator regression produced one
failure before correction; the corrected additive harness module has 42 PASS,
with no new platform skips. Original fixed test/fixture and historical evidence
were not modified. Later successful children do not establish a cause or repair
for the historical persisted-state discrepancy.

## CLI diagnostic line-ending correction

The initial CI run `38253316698` for source
`f8777babaa0c4f770a5bfb6ba80d1f7b1a485794` reproduced one failure in the new
privacy test on Windows/Python 3.13. The captured diagnostic had the expected
fixed message and the native Windows CRLF terminator; the new assertion had
incorrectly required an LF-only terminator.

The test now requires the **same exact message bytes** followed by
`os.linesep.encode("ascii")`. Exit code 2 and exclusion of the synthetic private
argument from stdout/stderr remain required. This changes only the new test's
platform-specific line-ending expectation, adds no test/skip, and does not alter
the CLI, frozen fixtures, migrations or secret-non-disclosure gate.
