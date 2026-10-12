"""Read-only stored-record checks shared by the API and offline copies."""

import hashlib
import sqlite3
from contextlib import closing
from time import monotonic as _clock

from nexus.private_storage import PrivateStorageError, configure_memory_temp

MAX_FTS_INSPECTION_BYTES = 128 * 1024 * 1024
MAX_INSPECTION_VALUE_BYTES = 2 * 1024 * 1024
FTS_INSPECTION_SECONDS = 10
FTS_SHADOW_COLUMNS = {
    "data": ("id", "block"), "idx": ("segid", "term", "pgno"),
    "docsize": ("id", "sz"), "content": ("id", "c0", "c1", "c2"), "config": ("k", "v"),
}

REFERENCE_QUERIES = {
    "orphan_import_batches":
        "SELECT count(*) FROM import_batches b WHERE NOT EXISTS "
        "(SELECT 1 FROM source_instances s WHERE s.id=b.source_id)",
    "incomplete_import_batches":
        "SELECT count(*) FROM import_batches WHERE ended_at IS NULL",
    "orphan_import_events":
        "SELECT count(*) FROM source_events e WHERE e.event_type='import.completed' "
        "AND NOT EXISTS (SELECT 1 FROM import_batches b "
        "WHERE e.external_event_key='import:'||b.id AND e.source_id=b.source_id "
        "AND e.raw_ref=b.import_hash AND b.ended_at IS NOT NULL)",
    "orphan_import_audits":
        "SELECT count(*) FROM audit_log a WHERE a.action='import' AND a.outcome='success' "
        "AND NOT EXISTS (SELECT 1 FROM import_batches b "
        "WHERE b.id=a.target AND b.ended_at IS NOT NULL)",
    "missing_import_events":
        "SELECT count(*) FROM import_batches b WHERE b.ended_at IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM source_events e "
        "WHERE e.event_type='import.completed' AND e.external_event_key='import:'||b.id "
        "AND e.source_id=b.source_id AND e.raw_ref=b.import_hash)",
    "missing_import_audits":
        "SELECT count(*) FROM import_batches b WHERE b.ended_at IS NOT NULL "
        "AND b.id NOT IN (SELECT a.target FROM audit_log a "
        "WHERE a.action='import' AND a.outcome='success')",
}


def require_references(db: sqlite3.Connection) -> None:
    """Metadata/FK guard within the caller's snapshot; no hash or FTS copy scan."""
    if not db.in_transaction:
        raise PrivateStorageError("Stored-record integrity is unavailable")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None or any(
        db.execute(query).fetchone()[0] for query in REFERENCE_QUERIES.values()
    ):
        raise PrivateStorageError("Stored-record integrity failed")


def _fts_index_errors(db: sqlite3.Connection) -> int:
    """Run native FTS integrity against an in-memory copy, never a source INSERT.

    SQLite's special INSERT integrity-check requires a write-capable connection
    even when it does not repair anything. Copy only the five known FTS5 shadow
    tables into an independent memory connection in this same Python runtime.
    The caller holds BEGIN so every copied table belongs to one source snapshot.
    This explicit deep check bounds copied values/pages and its scratch work;
    page requests use require_references instead. No source index is rebuilt.
    """
    deadline = _clock() + FTS_INSPECTION_SECONDS

    def check_deadline():
        if _clock() >= deadline:
            raise PrivateStorageError("Stored-record integrity inspection exceeded safety limits")

    # Check native lengths before any shadow value is fetched into Python. This
    # also refuses a forged large BLOB without allocating it in the inspection.
    total_bytes = 0
    for suffix, columns in FTS_SHADOW_COLUMNS.items():
        check_deadline()
        sizes = [f"coalesce(length(CAST({column} AS BLOB)),0)" for column in columns]
        size, largest = db.execute(
            f"SELECT coalesce(sum({'+'.join(sizes)}),0),"
            f"coalesce(max(max({','.join(sizes)})),0) FROM message_search_{suffix}"
        ).fetchone()
        total_bytes += size
        if total_bytes > MAX_FTS_INSPECTION_BYTES or largest > MAX_INSPECTION_VALUE_BYTES:
            raise PrivateStorageError("Stored-record integrity inspection exceeded safety limits")
        check_deadline()

    def bounded_rows(cursor):
        for row in cursor:
            check_deadline()
            yield row

    with closing(sqlite3.Connection(":memory:")) as scratch:
        configure_memory_temp(scratch)
        scratch.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_INSPECTION_VALUE_BYTES)
        page_size = scratch.execute("PRAGMA page_size").fetchone()[0]
        scratch.execute(f"PRAGMA max_page_count={max(1, MAX_FTS_INSPECTION_BYTES // page_size)}")
        scratch.set_progress_handler(lambda: int(_clock() >= deadline), 1000)
        scratch.execute("CREATE VIRTUAL TABLE message_search USING fts5("
                        "message_id UNINDEXED,title,content,tokenize='trigram')")
        for suffix in FTS_SHADOW_COLUMNS:
            table = "message_search_" + suffix
            scratch.execute("DELETE FROM " + table)
            cursor = db.execute("SELECT * FROM " + table)
            placeholders = ",".join("?" for _ in cursor.description)
            scratch.executemany("INSERT INTO " + table + " VALUES(" + placeholders + ")",
                                bounded_rows(cursor))
        try:
            scratch.execute("INSERT INTO message_search(message_search) VALUES('integrity-check')")
        except sqlite3.DatabaseError as error:
            if getattr(error, "sqlite_errorcode", 0) & 255 == sqlite3.SQLITE_CORRUPT:
                return 1
            raise
    return 0


def _content_hash_matches(content, digest) -> bool:
    # Ordinary SQLite TEXT columns have affinity, not strict storage types. A
    # damaged/imported DB can contain a BLOB; integrity must report counts rather
    # than fail with an AttributeError or coerce invalid bytes into history text.
    if type(content) is not str or type(digest) is not str:
        return False
    try:
        return hashlib.sha256(content.encode("utf-8")).hexdigest() == digest
    except UnicodeError:
        return False


def inspect_integrity(db: sqlite3.Connection) -> dict:
    # Hash inspection also must not allocate a forged multi-MiB stored BLOB.
    if db.execute("SELECT EXISTS(SELECT 1 FROM messages WHERE "
                  "length(CAST(content AS BLOB))>? OR length(CAST(content_sha256 AS BLOB))>?)",
                  (MAX_INSPECTION_VALUE_BYTES, MAX_INSPECTION_VALUE_BYTES)).fetchone()[0]:
        raise PrivateStorageError("Stored-record integrity inspection exceeded safety limits")
    fts_errors = _fts_index_errors(db)
    checks = {
        "sqlite_errors": sum(r[0] != "ok" for r in db.execute("PRAGMA integrity_check")),
        "foreign_key_errors": len(db.execute("PRAGMA foreign_key_check").fetchall()),
        **{code: db.execute(query).fetchone()[0] for code, query in REFERENCE_QUERIES.items()},
        # TEXT PRIMARY KEY does not imply NOT NULL in SQLite's ordinary tables.
        # Unreferenced invalid keys escape both SQLite and foreign-key checks.
        "invalid_primary_keys": sum(db.execute(
            f"SELECT count(*) FROM {table} WHERE typeof({key}) != 'text' "
            f"OR length({key})=0 OR instr({key},char(0))>0"
        ).fetchone()[0] for table, key in (
            ("source_instances", "id"), ("import_batches", "id"), ("projects", "id"),
            ("conversations", "id"), ("messages", "id"), ("source_events", "id"),
            ("tasks", "id"), ("evidence_links", "id"), ("sync_cursors", "source_id"),
            ("audit_log", "id"),
        )),
        "missing_search_rows": db.execute(
            "SELECT count(*) FROM (SELECT id FROM messages EXCEPT "
            "SELECT message_id FROM message_search)"
        ).fetchone()[0],
        "orphan_search_rows": db.execute(
            "SELECT count(*) FROM message_search f WHERE NOT EXISTS "
            "(SELECT 1 FROM messages m WHERE m.id=f.message_id)"
        ).fetchone()[0],
        "duplicate_search_keys": db.execute(
            "SELECT count(*) FROM (SELECT message_id FROM message_search "
            "GROUP BY message_id HAVING count(*)>1)"
        ).fetchone()[0],
        "stale_search_rows": db.execute(
            "SELECT count(*) FROM message_search f JOIN messages m ON m.id=f.message_id "
            "JOIN conversations c ON c.id=m.conversation_id "
            "WHERE f.content IS NOT m.content OR f.title IS NOT c.title"
        ).fetchone()[0],
        "content_hash_mismatches": sum(
            not _content_hash_matches(r[0], r[1])
            for r in db.execute("SELECT content,content_sha256 FROM messages")
        ),
        "fts_index_errors": fts_errors,
    }
    return {"ok": not any(checks.values()), "checks": checks,
            "coverage": "stored_records_only", "provider_completeness_verified": False}
