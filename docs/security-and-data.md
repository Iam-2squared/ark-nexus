# Security boundary and local data policy

This review covers the synthetic-only V1 implementation. It is not approval to ingest private provider history or to enable external AI execution.

## HTTP boundary

Use loopback binding only. Exact Host authorities and Origin values are restricted to localhost/127.0.0.1/[::1] on API port 8788 and development UI port 5173. Untrusted peers, foreign/null Origins, cross-site Fetch Metadata and ambiguous repeated security headers are rejected for reads as well as writes. Except fixed health metadata, routes also require an owner-local bearer key. Unsafe methods additionally require X-Nexus-Request: 1; no CORS permission is offered to foreign pages.

The custom write header is a browser CSRF boundary, **not a secret or authentication credential**. Authentication uses a separate random key in the owner-local data directory, or a configured NEXUS_API_TOKEN. The key is never returned by HTTP and is excluded from Git. Local processes without the key cannot read private endpoints or mutate data. Processes running as the same OS user can read that user's key and database and remain outside this protection boundary. The UI keeps the key only in tab session storage; locking clears it and visible private records. Invalid keys return 401 and clear the dashboard snapshot. Bind-only, Host and Origin checks must not be represented as remote-access authorization. Do not put this API behind a network proxy.

The complete ASGI body stream is bounded before FastAPI parses JSON or spools multipart. Ordinary requests allow 64 KiB; the import envelope allows 8 MiB plus 64 KiB overhead, and the actual upload remains limited to 8 MiB. Both declared lengths and chunked actual bodies are checked. Validation errors omit offending inputs; storage errors return a generic unavailable response. Run with access logging disabled when private metadata could appear in URL query strings.

## Input and instruction handling

- No archive extraction. Unsafe paths, symlinks, duplicate entries, encryption, bad CRC, unsupported compression, excessive file count/expanded size/compression ratio are rejected.
- Synthetic ZIP: one JSON file, at most 200 entries, 32 MiB combined declared expansion, maximum 100:1 ratio. Highly compressible otherwise-valid data can be rejected by this safety policy.
- UTF-8 JSON only; duplicate object keys, NaN/Infinity literals, excessive nesting/node counts, invalid Unicode/NUL in stored strings, duplicate identities and ambiguous/invalid timestamps are rejected.
- Source content is data. React renders it as text, not HTML. There is no model invocation, subprocess execution, task dispatch or instruction-to-approval conversion in an import.
- Synthetic source role labels are preserved. Timestamp strings require timezone-aware ISO 8601 and retain the original representation.
- A changed message identity aborts all conversations, messages, import receipt, source event and audit writes in that batch.

## SQLite and retention

Imports and migrations acquire a write transaction before identity/schema checks. Failed imports leave no partial rows. Each schema migration is applied once; added search-maintenance triggers and indexes preserve existing migrations and data. Concurrent identical imports produce one copy. Titles and first/last source times update after incremental imports.

Default database: Windows LOCALAPPDATA/ARK-Nexus/nexus.sqlite3; Linux ~/.local/share/ark-nexus/nexus.sqlite3. NEXUS_DATA_DIR can override it. Module import creates no profile database; server startup does. Development tests use synthetic data in isolated temporary directories.

Database/key paths containing symlinks, NTFS junctions or hard links are rejected before writing. SQLite main/-journal/-wal/-shm paths are rechecked before each Store connection; other Windows reparse points are rejected too. Existing POSIX storage parents/files must be owner-only; shared permissions are refused without changing the existing directory. New POSIX directories/files use 0700/0600. Existing access-key paths must be regular files and contain at most 256 token characters with only an optional LF/CRLF ending; malformed files are rejected without echoing contents or changing directory permissions. Windows application storage still inherits its directory ACL; the new probe protects only a new owned synthetic directory. POSIX mode assertions do not verify Windows ACL behavior. SQLite storage is plaintext. See [retention/deletion/encryption design](retention-and-deletion-design.md).

Retention is indefinite until the owner requests deletion. There is no HTTP deletion endpoint, scheduled cleanup or source-deletion propagation. Destructive removal or replacing an existing database requires separate explicit authorization. Raw uploaded archives, filenames and message payloads are not stored in audit entries. Successful import receipts preserve batch hashes/counts/version/source; rejected input is not retained as payload or a successful receipt.

## Integrity and recovery

GET /api/v1/integrity checks SQLite and foreign keys, missing/orphan/duplicate/stale search rows and content-hash mismatches. Responses contain counts, not conversation content. It checks stored records only: it cannot establish completeness of an export or detect provider records never observed.

Use the SQLite backup API for a consistent offline copy:

    python -m nexus.maintenance SOURCE_DATABASE NEW_DESTINATION_DATABASE

The command refuses an existing destination or orphan destination sidecars, checks SQLite/FK/FTS/content-hash integrity in one source read snapshot and again in the copy, and does not overwrite the source. Both SQLite connections close before failure cleanup; only the new destination with its original file identity can be removed. CLI errors use a fixed message without private paths or traceback. The same command can restore a backup to a *new* location. Confirm stored-record integrity and counts before explicitly choosing that restored path for a future server start. This does not automatically switch the running application.

The local owner controls the private directory; path checks are not a defense against a privileged or same-user process racing filesystem changes. A portable path policy rejects Windows ADS colons, reserved device names, ambiguous trailing dots/spaces and UNC/device volumes. Windows regular runtime DACL hardening and short-name/network-filesystem behavior have not been qualified. Do not use a shared, network or synchronized folder for private profiles/backups. An isolated probe is not approval of the default profile.

## Remaining gates

- Owner-approved real-format samples from both providers: BLOCKED.
- Per-user bearer authentication is implemented and regression-tested; owner-machine key-directory ACLs and hostile same-user process risks still require review.
- Windows synthetic-directory DACL/listener probe: implemented; new-HEAD Windows CI evidence required. Owner-machine and private-profile ACL evidence remain NOT RUN. See [Windows guide](windows-machine-validation.md).
- Local Chromium execution could not start because the download failed. Actual API/UI browser tests are added to GitHub Actions and must pass at the new HEAD. Owner-machine Windows/browser/offline cold startup remains unverified.
- Large real exports, attachments, branch/revision semantics, background sync and encrypted storage: not implemented.
