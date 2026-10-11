# V1 evaluation definition and evidence

The initial PASS evidence and test fixture files are preserved. New regression cases add coverage; they do not replace or weaken the existing 1,000-message reimport or 30 token-search assertions.

Baseline inspected: branch feature/v1-unified-history-scaffold at a2aa0e9c739380695842973b2a095e8f195dd354; main 91a493a9ffb636c85b016874f1f721685adab12e. Only Draft PR #1 was open and no reviews/comments were present. GitHub Actions run 38116378322 passed all 5 jobs. Earlier run 38116329877 failed Ruff F841 for an unused variable; that baseline failure had already been corrected.

## Frozen completion gates

| Evaluation | Required result | Evidence / state |
|---|---|---|
| Backend CI | Linux/Windows x Python 3.12/3.13 all PASS at the new HEAD | Final GitHub run must be checked after commit |
| Frontend | TypeScript/Vite build PASS | Local build PASS; new-HEAD CI required |
| 1,000-message reimport | Zero additional conversations/messages; 1,000 duplicates reported | Original test retained and PASS locally |
| Search regression | Original fixed 30 token assertions plus additive fixed 30 mixed-language cases | PASS locally; new cases include Japanese short strings, literal %, _, backslash, quotes, filters and provider/account isolation |
| Provider distinction | Source/provider/account IDs and original message/conversation IDs preserved | Automated provenance/isolation checks |
| Abnormal input | Safe rejection and full transaction rollback | Host/Origin/body, archive, JSON, Unicode, timestamp and identity tests |
| Stored history integrity | Detect index gaps/duplicates/staleness and content hash mismatch; preserve recovery | Integrity, concurrent imports/migrations, copy-to-new-location roundtrip tests |
| Actual provider formats | Approved anonymized current ChatGPT and Claude samples PASS | **BLOCKED for both**; no samples provided |

Updated migration assertions now require versions [1,2], because an additive migration was introduced; repeatability remains required. This is not a relaxed schema or import gate.

## Reproduction

Backend:

    python -m pip install -e ".[dev]"
    python -m pytest -q --basetemp=.pytest-tmp
    python -m ruff check .

Frontend (apps/web):

    npm ci --no-audit --no-fund
    npm test
    npm run build

The frontend DOM tests exercise local authentication, UI requests, provenance, imports, disabled connectors and failure states with synthetic HTTP responses. jsdom file-validation behavior differs from a native browser, so upload form handlers are exercised after file selection; actual file validation/submit behavior is separately tested by Chromium. They do not replace real Chromium layout, cross-browser behavior or owner-machine offline evidence. Local Playwright execution could not start because Chromium was absent and the download returned invalid archives; no local browser PASS is claimed. GitHub Actions runs two real Chromium API/UI scenarios, including authenticated 1,000-message import/reimport, project mapping, Japanese search, long-history paging, inert imported HTML, mobile overflow and lock behavior. Its current-HEAD result must be verified before claiming browser PASS.

Windows POSIX permission assertions are explicitly skipped because they cannot verify Windows ACLs. Symlink tests can skip when the runner lacks creation rights; report those separately from executed checks.

First expanded-CI run 38118124755 at adbb95b15b5c6e03a5f424a5e4b1d7afbecbbaf5 failed 3/5 jobs. Both Windows jobs hit the 32,767-character environment-variable limit because pytest expanded a large ZIP byte parameter into a case name. Explicit short case IDs retain the exact archive contents and rejection assertions. Chromium completed the 1,000-message import/reimport and message paging, then failed to locate the exact search project label. Explicit filter aria-labels fix the label association; the browser assertion and timeout remain unchanged. Additional key-file failures were reproduced before fixing validation, and NTFS junction rejection is covered by a platform-independent regression and a real Windows-only filesystem test. These failures are retained as evidence; final new-HEAD CI must pass.

The integrity-check UI also retained an unlocked snapshot after a 401; a failing DOM reproduction was added before routing that error through the shared lock/clear handler. Each new integrity check clears its previous result before requesting fresh evidence.

Run 38118467273 at 9355166c61d17c04e8a1c40b64e50d2c325dc941 confirmed the ZIP-case-name fix and real Windows NTFS-junction rejection, but still failed 3/5 jobs. Windows raises EACCES for an exclusive-open directory, so the non-file check now precedes opening as well as handling EEXIST. Chromium reached the integrity result after completing Japanese search/pagination; its generic status locator was ambiguous with the retained import receipt result. Distinct accessible result labels and a failing combined-result DOM reproduction preserve both expected result assertions. No result count, browser timeout or abnormal-input gate was reduced.

Run 38118614549 at 172be9d09efc3f58febccb88e94b61562f162028 passed all 5 jobs, including 2 actual Chromium scenarios, 16 DOM tests, build and all four backend environments (120 passed plus one platform-specific skip each). Independent synthetic-input audit then reproduced unhandled zlib.error and LZMAError for corrupt compressed ZIP streams. New DEFLATE/LZMA/BZip2 regression cases require generic HTTP 422 and zero stored sources/conversations/messages/import receipts. Decompression errors are converted to ImportProblem before any store operation; the follow-up HEAD must receive its own CI evidence.

V1 official PASS stays **BLOCKED** until the actual-format and remaining private-data security gates pass. Do not report a percentage without a separately agreed gate-weighting method.
