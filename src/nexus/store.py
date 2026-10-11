"""Small SQLite persistence layer with an idempotent migration and provenance-preserving imports."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from nexus.private_storage import prepare_database


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class Store:
    def __init__(self, path: Path):
        self.path = prepare_database(path)
        self.migrate()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                         "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            migrations = sorted(resources.files("nexus").joinpath("migrations").iterdir(),
                                key=lambda file: file.name)
            for file in migrations:
                if file.name.endswith(".sql"):
                    version = int(file.name.split("_", 1)[0])
                    if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?",
                                    (version,)).fetchone():
                        continue
                    # complete_statement preserves trigger bodies while keeping one transaction.
                    statement = ""
                    for line in file.read_text(encoding="utf-8").splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            conn.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise ValueError("Incomplete database migration")
                    conn.execute("INSERT INTO schema_migrations VALUES (?,?)", (version, utcnow()))

    def import_conversations(
        self,
        *,
        provider: str,
        account_alias: str,
        import_hash: str,
        parser_version: str,
        conversations: list,
    ) -> dict:
        batch_id = new_id()
        now = utcnow()
        inserted_messages = 0
        inserted_conversations = 0
        seen_messages = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            source_id_row = db.execute(
                "SELECT id FROM source_instances WHERE provider=? AND product=? AND account_alias=?",
                (provider, "consumer_chat", account_alias),
            ).fetchone()
            if source_id_row:
                source_id = source_id_row["id"]
            else:
                source_id = new_id()
                capability = json.dumps(
                    {"read_history": False, "manual_fixture_import": True,
                     "read_live_status": False, "dispatch_new": False,
                     "resume_existing": False, "scope": "authorized synthetic import",
                     "limitations": "Current real export schemas NOT yet validated"}
                )
                db.execute(
                    "INSERT INTO source_instances(id,provider,product,account_alias,capabilities_json) "
                    "VALUES(?,?,?,?,?)",
                    (source_id, provider, "consumer_chat", account_alias, capability),
                )
            db.execute(
                "INSERT INTO import_batches(id,source_id,import_hash,parser_version,started_at) "
                "VALUES(?,?,?,?,?)",
                (batch_id, source_id, import_hash, parser_version, now),
            )
            for conv in conversations:
                row = db.execute(
                    "SELECT id FROM conversations WHERE source_id=? AND external_id=?",
                    (source_id, conv.external_id),
                ).fetchone()
                if row:
                    conv_id = row["id"]
                    db.execute("UPDATE conversations SET title=? WHERE id=?", (conv.title, conv_id))
                else:
                    conv_id = new_id()
                    db.execute(
                        "INSERT INTO conversations(id,source_id,external_id,title,first_at,last_at) "
                        "VALUES(?,?,?,?,?,?)",
                        (conv_id, source_id, conv.external_id, conv.title,
                         conv.messages[0].occurred_at if conv.messages else None,
                         conv.messages[-1].occurred_at if conv.messages else None),
                    )
                    inserted_conversations += 1
                for msg in conv.messages:
                    seen_messages += 1
                    previous = db.execute(
                        "SELECT content_sha256,role,occurred_at FROM messages "
                        "WHERE conversation_id=? AND external_id=?",
                        (conv_id, msg.external_id),
                    ).fetchone()
                    if previous:
                        if (previous["content_sha256"] != msg.content_sha256
                                or previous["role"] != msg.role
                                or previous["occurred_at"] != msg.occurred_at):
                            raise ValueError(
                                "Source message ID reused with changed contents; "
                                "immutable V1 history requires a revision-aware adapter"
                            )
                        continue
                    db.execute(
                        "INSERT INTO messages"
                        "(id,conversation_id,external_id,role,content,occurred_at,observed_at,content_sha256) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (new_id(), conv_id, msg.external_id, msg.role, msg.content,
                         msg.occurred_at, now, msg.content_sha256),
                    )
                    inserted_messages += 1
                stamps = [r[0] for r in db.execute(
                    "SELECT occurred_at FROM messages WHERE conversation_id=? "
                    "AND occurred_at IS NOT NULL", (conv_id,)
                )]
                if stamps:
                    ordered = sorted(stamps, key=datetime.fromisoformat)
                    db.execute("UPDATE conversations SET first_at=?,last_at=? WHERE id=?",
                               (ordered[0], ordered[-1], conv_id))
            counts = {
                "conversations_seen": len(conversations),
                "conversations_inserted": inserted_conversations,
                "messages_seen": seen_messages,
                "messages_inserted": inserted_messages,
                "messages_duplicates": seen_messages - inserted_messages,
                "messages_rejected": 0,
            }
            db.execute(
                "UPDATE import_batches SET ended_at=?,counts_json=? WHERE id=?",
                (utcnow(), json.dumps(counts), batch_id),
            )
            db.execute(
                "UPDATE source_instances SET last_sync_at=?,sync_state='manual_import' WHERE id=?",
                (now, source_id),
            )
            db.execute(
                "INSERT INTO source_events"
                "(id,source_id,external_event_key,event_type,occurred_at,observed_at,raw_ref) "
                "VALUES(?,?,?,?,?,?,?)",
                (new_id(), source_id, f"import:{batch_id}", "import.completed", now, now, import_hash),
            )
            db.execute(
                "INSERT INTO audit_log(id,action,actor,target,outcome,at) VALUES(?,?,?,?,?,?)",
                (new_id(), "import", "local_user", batch_id, "success", now),
            )
        return {"id": batch_id, "source_id": source_id, "status": "imported", "counts": counts,
                "parser_version": parser_version, "sync_mode": "manual"}

    def sources(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM source_instances ORDER BY provider,account_alias").fetchall()
        return [{**{key: r[key] for key in r.keys() if key != "capabilities_json"},
                 "capabilities": {"read_history": False, "manual_fixture_import": True,
                                  "read_live_status": False, "dispatch_new": False,
                                  "resume_existing": False},
                 "connection_state": "manual_import", "data_kind": "synthetic",
                 "sync_mode": "manual", "coverage": "synthetic_only"} for r in rows]

    def overview(self) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
            counts = {name: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                      for name, table in (("sources", "source_instances"),
                                          ("conversations", "conversations"),
                                          ("messages", "messages"), ("projects", "projects"),
                                          ("imports", "import_batches"))}
        return {"counts": counts, "data_kind": "synthetic", "external_providers_connected": False}

    def integrity_report(self) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
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

    def _page(self, sql: str, params: list | tuple, limit: int, offset: int) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
            total = db.execute(f"SELECT count(*) FROM ({sql})", params).fetchone()[0]
            rows = db.execute(sql + " LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
        items = [dict(row) for row in rows]
        next_offset = offset + len(items)
        return {"items": items, "total": total, "limit": limit, "offset": offset,
                "next_offset": next_offset if next_offset < total else None}

    def imports(self, limit: int = 100, offset: int = 0) -> dict:
        page = self._page(
            "SELECT b.*,s.provider,s.account_alias FROM import_batches b "
            "JOIN source_instances s ON s.id=b.source_id ORDER BY b.rowid DESC", [], limit, offset
        )
        page["items"] = [{**r, "counts": json.loads(r["counts_json"]),
                          "errors": json.loads(r["errors_json"]), "status": "imported",
                          "data_kind": "synthetic"} for r in page["items"]]
        return page

    def receipt(self, batch_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
        return ({**dict(row), "counts": json.loads(row["counts_json"]),
                 "errors": json.loads(row["errors_json"])} if row else None)

    def conversations(self, source_id: str | None = None, project_id: str | None = None):
        return self.conversations_page(source_id, project_id)["items"]

    def conversations_page(self, source_id: str | None = None, project_id: str | None = None,
                           limit: int = 500, offset: int = 0):
        where = []
        params = []
        if source_id:
            where.append("c.source_id=?")
            params.append(source_id)
        if project_id:
            where.append("c.project_id=?")
            params.append(project_id)
        clause = " AND ".join(where) if where else "1=1"
        return self._page(
                f"SELECT c.*,s.provider,s.account_alias,"
                "(SELECT count(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
                f"FROM conversations c JOIN source_instances s ON s.id=c.source_id "
                f"WHERE {clause} ORDER BY c.rowid DESC", params, limit, offset
        )

    def messages(self, conversation_id: str) -> list[dict]:
        page = self.messages_page(conversation_id)
        return page["items"] if page else []

    def messages_page(self, conversation_id: str, limit: int = 200, offset: int = 0) -> dict | None:
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
                return None
        return self._page(
            "SELECT m.* FROM messages m WHERE m.conversation_id=? ORDER BY m.rowid ASC",
            (conversation_id,), limit, offset
        )

    def search(self, q: str, project_id: str | None, source_id: str | None) -> list[dict]:
        return self.search_page(q, project_id, source_id)["items"]

    def search_page(self, q: str, project_id: str | None, source_id: str | None,
                    limit: int = 100, offset: int = 0) -> dict:
        if not q.strip():
            return {"items": [], "total": 0, "limit": limit, "offset": offset, "next_offset": None}
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        needle = f"%{escaped}%"
        return self._page(
                "SELECT m.id AS message_id,m.external_id AS external_message_id,"
                "m.role,m.content,m.occurred_at,"
                "c.id AS conversation_id,c.external_id AS external_conversation_id,"
                "c.title,c.project_id,s.id AS source_id,"
                "s.provider,s.account_alias "
                "FROM message_search f JOIN messages m ON m.id=f.message_id "
                "JOIN conversations c ON c.id=m.conversation_id "
                "JOIN source_instances s ON s.id=c.source_id "
                "WHERE (f.content LIKE ? ESCAPE '\\' OR f.title LIKE ? ESCAPE '\\') "
                "AND (? IS NULL OR c.project_id=?) AND (? IS NULL OR c.source_id=?) "
                "ORDER BY m.rowid DESC",
                (needle, needle, project_id, project_id, source_id, source_id), limit, offset
        )

    def projects(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT p.*,(SELECT count(*) FROM conversations c "
                              "WHERE c.project_id=p.id) conversation_count "
                              "FROM projects p ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def create_project(self, name: str, repo_url: str | None) -> dict:
        record = {"id": new_id(), "name": name, "repo_url": repo_url, "sharing_policy": "none"}
        with self.connect() as db:
            db.execute(
                "INSERT INTO projects(id,name,repo_url,sharing_policy) VALUES(?,?,?,?)",
                (record["id"], name, repo_url, "none"),
            )
        return record

    def assign_conversation(self, conversation_id: str, project_id: str | None) -> bool:
        with self.connect() as db:
            if project_id and not db.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone():
                raise ValueError("unknown project")
            changed = db.execute(
                "UPDATE conversations SET project_id=? WHERE id=?", (project_id, conversation_id)
            ).rowcount
        return changed > 0
