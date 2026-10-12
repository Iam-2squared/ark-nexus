# Input boundary forensics — 2026-10-12

Scope: synthetic inputs only, baseline source
`18e61002a7f89bc065c296e100a574bf10ff1ac4`. No live provider parser,
private export, OS temporary-directory change, or database repair is involved.
This investigation is independent of the unresolved 10k database anomaly;
these ZIP reproductions are not its cause or a claimed fix for it.

## Reproduction and fix

The additive suite initially produced **24 FAIL / 16 PASS**. Failures are
parameterized cases, not 24 separate vulnerabilities. Small in-memory archives
are sufficient; the largest corrupt decoded example adds 5,000 synthetic
whitespace bytes, not an unbounded decompression workload.

| Boundary | Baseline observation | Current behavior |
| --- | --- | --- |
| Complete compressed stream | DEFLATE, BZip2, and ZIP-LZMA accepted a stream with the last byte removed when its decoded prefix still matched the declared CRC and size. | Decoder EOF is required. Truncation is rejected with fixed `Invalid ZIP archive`. |
| Actual decoded size | All three codecs accepted a false smaller size plus a CRC over only the visible JSON prefix. A false larger size was also accepted. | Decoding is capped at the declared size plus one byte, within the existing 32 MiB limit, and the actual size must match exactly. Nothing is silently truncated into valid JSON. |
| Compressed tail | All three codecs ignored synthetic bytes included after their compressed end marker. | One complete compressed stream is required; unused input or DEFLATE unconsumed input is rejected. |
| Local header versus directory | All four supported codecs accepted conflicting compression-method or encryption-flag declarations between the local header and central directory. | Those declarations must match before decoding. Stdlib filename, overlap, encryption, and unsupported-method checks remain in use. |
| Archive filename UTF-8 | Malformed directory or local-header UTF-8 raised `UnicodeDecodeError` outside the existing import-error conversion. | Fixed HTTP 422; no import or receipt is stored. |
| ZIP-LZMA dictionary | A forged dictionary value reached decoder initialization without a V1 budget check. The reproduction uses a rejecting test double, not a large allocation. | Dictionary sizes above 32 MiB are refused before native decoder construction. |
| ZIP-LZMA framing | A stream without the explicit EOS flag was accepted without a qualified framing contract. | V1 supports explicit EOS framing only; other LZMA framing is refused. |

The stricter reader uses the public bounded decoder APIs and public `ZipInfo`
header offsets. It does not access `ZipExtFile` private decompressor fields,
extract files, modify globals, or invoke subprocesses. STORED, DEFLATE, BZip2,
and explicit-EOS ZIP-LZMA remain supported. All four succeed with ordinary
headers, data descriptors, ZIP64 local headers, and archive prefixes.

The ZIP specification permits LZMA without an EOS marker. Its rejection here is
an explicit V1 safety restriction, not a claim that every such ZIP is malformed.
Likewise, a dictionary above 32 MiB is unqualified for this bounded importer.
No new real-format compatibility is claimed.

## Validation and limits

`tests/test_forensic_input_boundaries.py` adds **40 cases**: the 24 reproductions
plus 16 valid archive/header controls. Each applicable HTTP regression requires
fixed 422 output and zero persisted records, while valid controls require 201
and logical integrity. Existing archive limits and HTTP/multipart lifecycle
suites are retained unchanged.

Local focused validation: **206 PASS**, Python 3.12.14, no new platform skip.
Ruff passes for the changed importer and additive suite. The final source HEAD's
Linux/Windows matrix remains a separate CI requirement, not inferred from this
local run.

Unchanged limits: upload 8 MiB, envelope reception 15 seconds, two active
imports, combined declared archive expansion 32 MiB, maximum compression ratio
100:1, at most 200 ZIP entries, and at most 50,000 normalized messages. Bounded
decoding now verifies actual JSON expansion as well. It does not prove a bound
on total process RSS, CPU time, or all native codec overhead under host-wide
memory exhaustion. No private data may be imported while V1 remains BLOCKED.

Official API/format references:

- [Python 3.12 zlib decoder](https://docs.python.org/3.12/library/zlib.html#zlib.Decompress.decompress)
- [Python 3.12 BZip2 decoder](https://docs.python.org/3.12/library/bz2.html#bz2.BZ2Decompressor)
- [Python 3.12 LZMA decoder](https://docs.python.org/3.12/library/lzma.html#lzma.LZMADecompressor)
- [PKWARE ZIP specification](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT), local header and LZMA framing/property sections.
