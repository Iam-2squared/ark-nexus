"""Read-only stored-record checks shared by the API and offline copies."""

import hashlib
import sqlite3


def inspect_integrity(db: sqlite3.Connection) -> dict:
    checks = {
        "sqlite_errors": sum(r[0] != "ok" for r in db.execute("PRAGMA integrity_check")),
        "foreign_key_errors": len(db.execute("PRAGMA foreign_key_check").fetchall()),
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
            "WHERE f.content != m.content OR f.title != c.title"
        ).fetchone()[0],
        "content_hash_mismatches": sum(
            hashlib.sha256(r[0].encode("utf-8")).hexdigest() != r[1]
            for r in db.execute("SELECT content,content_sha256 FROM messages")
        ),
    }
    return {"ok": not any(checks.values()), "checks": checks,
            "coverage": "stored_records_only", "provider_completeness_verified": False}
