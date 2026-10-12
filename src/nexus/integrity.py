"""Read-only stored-record checks shared by the API and offline copies."""

import hashlib
import sqlite3


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
    checks = {
        "sqlite_errors": sum(r[0] != "ok" for r in db.execute("PRAGMA integrity_check")),
        "foreign_key_errors": len(db.execute("PRAGMA foreign_key_check").fetchall()),
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
    }
    return {"ok": not any(checks.values()), "checks": checks,
            "coverage": "stored_records_only", "provider_completeness_verified": False}
