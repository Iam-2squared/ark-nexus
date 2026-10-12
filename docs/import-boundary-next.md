# Import request boundary: next batch

The implementation remains synthetic-fixture-only. Real private exports are
prohibited while their adapter and storage qualification gates are BLOCKED.

## Reproduction and fixes

Baseline source: `79e56eb20a581825b0ce2392c82fc0d7127918fa`.
The first additive run contained 26 tests: **21 FAIL, 5 PASS** before fixes.
Failures are parameterized reproductions, not 21 distinct vulnerabilities.
Review of the first fix then reproduced two additional raw-ASGI coding values
with non-ASCII whitespace or a newline; only HTTP space/tab trimming is allowed.

| Boundary | Reproduction | Result after the fix |
| --- | --- | --- |
| Method-specific body cap | `GET`, `PATCH`, and `HEAD /api/v1/imports` accepted a 65,537-byte body at the middleware level, with declared length or chunked framing, although these requests do not hold an import permit. | Only `POST /api/v1/imports` receives the larger import envelope. Other methods retain the 64 KiB cap. Declared oversize bodies are refused before reading; chunked excess is refused before the application handler. |
| Transfer coding | Raw ASGI requests declaring `gzip`, `gzip, chunked`, or `chunked, chunked` reached the handler. | The boundary accepts one case-insensitive `chunked` coding and rejects unsupported combinations before body consumption. This supplements the HTTP server's parser; it is not evidence of an h11 framing bypass. |
| Duplicate parameters | The installed multipart option parser selected the last `boundary`, `charset`, `name`, or `filename`, including case variants and duplicates with identical values. Synthetic imports returned 201. | A bounded syntax check rejects duplicate parameters before the upstream parser can discard their evidence. Names/filenames, boundary, and charset have explicit parameter allowlists. |
| Conflicting part encoding | Text labeled `iso-8859-1`, repeated part charset labels, and `Content-Transfer-Encoding: base64` were ignored while raw UTF-8 content was accepted. | Part encoding labels must agree with the UTF-8-only contract. Content transfer encoding has no supported V1 interpretation and is refused. |

The fixes change only `security.py` and `memory_upload.py`. They do not alter
the 8 MiB upload cap, 15-second reception deadline, two concurrent import
permits, 32 MiB ZIP expansion cap, or 50,000-message cap. No tempfile factory,
global environment value, OS setting, database migration, or external
authentication is introduced.

## Additive validation

`tests/test_next_import_boundaries.py` contains **37 synthetic cases**. It also
checks malformed/unsupported parameter syntax, cleanup after a file was staged
before a later parameter error, permit reuse after three refused requests, and
successful subsequent import with logical database integrity. Quoted filenames
containing Japanese characters, semicolons, and escaped quotes survive 1-byte,
7-byte, and complete-envelope stream chunks.

The focused run includes the new suite plus existing multipart containment,
interruption/cancellation, and HTTP security suites. It uses a new test root
under the checkout's ignored `tmp/` tree. Platform-wide CI remains the root
batch's responsibility; local PASS is not Windows owner-machine evidence.

Multipart staging still owns only in-memory buffers and closes them on all
parser failures. The new checks do not qualify SQLite statement journals,
crash remnants, pagefile/swap, or normal-profile ACLs. Those gates retain their
individual NOT RUN/BLOCKED status until separately measured and reviewed.
