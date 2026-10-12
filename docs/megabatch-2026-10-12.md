# 2026-10-12 mega-batch — changes and evidence

## CI follow-up: explicit conversation filter labels

Source `79c1abe365f6fe11feb2f286955735f89fa5d92f` / run
[38218223288](https://github.com/Iam-2squared/ark-nexus/actions/runs/38218223288)
completed4/5 PASS. Both Linux jobs512+3 skips and both Windows jobs513+2 passed;
DOM44/build passed. Chromium6/7 passed, including the original five scenarios.
The added scenario timed out at the exact Conversation source label: the native
wrapped select did not have the intended explicit accessible name. One additive
DOM reproduction failed before adding aria-label to the two conversation filters.
DOM45/build then passed locally. Original exact selectors, seven scenarios and
30-second timeout are unchanged. The follow-up HEAD requires its own full CI;
the4/5 failure is retained and not described as a complete PASS.

Scope: **Iam-2squared/ark-nexus only**. Draft PR1 stays Draft/unmerged.
Start main `91a493a9ffb636c85b016874f1f721685adab12e`; start feature
`0f99177c731edf64b13794d7f96cb5f4791a29ab`. Start
[run38211053827](https://github.com/Iam-2squared/ark-nexus/actions/runs/38211053827)
was5/5 PASS: Linux193+3 platform skips each, Windows194+2 each, DOM24/build/Chromium5.
This historical result is not reused for the new source. Exact final HEAD/CI and
artifact inspection are recorded in the Draft PR.

## Changes / reproductions

| Priority | Implementation and evidence |
|---|---|
| P0-A | Memory-only bounded multipart, complete envelope and buffer cleanup; SQLite MEMORY/build checks; body15s/two import permits. Temp suite first17 FAIL/1 PASS. Full private storage qualification remains BLOCKED. |
| P0-B | Forwarded/proxy headers, duplicate Fetch Metadata and ambiguous framing reject; strict original UTF-8/NUL paths/queries/project fields;64-bit offset; storage failure generic503. Security suite first41 FAIL/24 PASS plus two storage misclassification FAIL. |
| P0-C | NULL FTS title/content now fail integrity/backup. Interrupted copy removes only its new owned destination. Four failing cases preceded fixes.10k pagination,5k parallel import/retry, atomic migration failure and new-path restore added. |
| P0-D | Four OS/Python jobs, Ruff/build and originalDOM24/Chromium5 retained. Additive20 DOM/two Chromium. Artifact allowlists/retention and owner classifications unchanged. |
| P1-A/B | Parser identity/type/hash and shared-review mutation guards;169 additive cases. Manifest-only preflight and pure source/cursor/task-state simulation read no exports and enable no dispatch. |
| P1-C | Synchronous write guards, abort/session handling, late401 after another reload failure, page-only back/forward/drafts, conversation filters, safe paging, explicit retries, stale/empty states and aria-live. Initial UI12 FAIL then four more. |
| P1-D/E | Windows probe/report Gates unchanged. Opt-in benchmark requires NEW checkout-local tmp, refuses existing/outside/link paths and emits conditions/counts only. |
| P2 | Advisory-based minimal dependency floors and explicit plaintext/temp/ACL risks. Encryption/deletion remain inactive. |

Initial full integration added **319 backend cases**: temp25, security82,
integrity20, benchmark23, adapter hardening19, manifest34, connector simulation116.
Local Linux/CPython3.12.14:512 PASS/3 SKIP; Ruff/pip check PASS. DOM44/44 and
TypeScript/Vite PASS. Local browser download returned invalid archives: Chromium
NOT RUN locally, current-source CI evaluated separately. These are pre-commit
results; final HEAD requires independent CI.

Original fixtures/migrations,1,000-message zero-addition reimport, fixed30+30
search, originalDOM24/Chromium5 were not edited or weakened. One initial10k search
anomaly (empty DB result) did not recur in isolated/full data/integrated runs;
cause unconfirmed, not counted as fixed.

## UI preservation

style.css, CosmicShell, the white N/halo/ring/six-star design and headings are
unchanged. App changes behavior and operational feedback. Start-CI1440x1000
desktop/mobile390 images were visually inspected; exact four-PNG archive and
SHA-256 verified. New-source images need their own inspection, not owner evidence.

## Reference benchmark (no retrofitted target)

One sample/operation; Linux x86_64, CPython3.12.14, SQLite3.53.1,9 logical CPUs,
tracemalloc enabled. Parser/store benchmark, not HTTP/browser. CPU model, physical
RAM/full RSS not measured. Measured on this batch's implementation before commit.

| Messages | Import seconds | Japanese search ms | Tracked Python peak bytes |
|---:|---:|---:|---:|
|1,000|0.094922|7.681|793,734|
|10,000|0.966280|53.005|7,466,596|
|50,000|7.056782|285.137|37,376,332|

All stages: reimport inserted0, exact search totals, empty end page, FK/FTS/hash
integrity true, nine compared logical tables identical after backup/restore.
This is a baseline, not performance PASS or owner hardware evidence.

    python -m nexus.synthetic_benchmark --root tmp/synthetic-benchmark/NEW_NAME --stages 1000 10000 50000

Use a new name each time; share only reviewed summary report.json if needed, never
the DB/directory/key/log.50k is opt-in, separate from normal CI's10k stress.

## Remaining gates

| Gate | State / reason |
|---|---|
|Consumer ChatGPT/Claude real-format|BLOCKED/disabled; approved anonymized samples absent|
|Owner Windows offline/browser/other-user/normal-profile ACL|NOT RUN; owner evidence absent|
|Private storage qualification|BLOCKED; statement journal/native capture/ACL/crash surfaces remain, SQLite plaintext|
|External connector/dispatch/resume/sync|Unimplemented/not_connected/execution disabled|
|V2–V5|LOCKED; pure contracts are research, not runtime completion|
|Encryption/deletion/retention cleanup|Design only/inactive|

See [temp gates](temp-containment.md), [adapter preflight](adapter-preflight.md),
[connector research](connector-contracts.md), [owner checklist](windows-owner-checklist.md).
Other repo/project writes, paid APIs, AI login, private transmission, destructive
user-data deletion and OS settings/normal-profile ACL changes:0.
