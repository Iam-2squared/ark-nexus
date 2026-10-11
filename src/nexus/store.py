"""Small SQLite persistence layer with an idempotent migration and provenance-preserving imports."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
        sql = resources.files("nexus").joinpath("migrations/0001_init.sql").read_text()
        with self.connect() as conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)",
                (1, utcnow()),
            )

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
            source_id_row = db.execute(
                "SELECT id FROM source_instances WHERE provider=? AND product=? AND account_alias=?",
                (provider, "consumer_chat", account_alias),
            ).fetchone()
            if source_id_row:
                source_id = source_id_row["id"]
            else:
                source_id = new_id()
                capability = json.dumps(
                    {"read_history": True, "read_live_status": False, "dispatch_new": False,
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
                        "SELECT content_sha256,role FROM messages "
                        "WHERE conversation_id=? AND external_id=?",
                        (conv_id, msg.external_id),
                    ).fetchone()
                    if previous:
                        if previous["content_sha256"] != msg.content_sha256 or previous["role"] != msg.role:
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
        return [{**dict(r), "capabilities": json.loads(r["capabilities_json"]),
                 "sync_mode": "manual", "coverage": "partial"} for r in rows]

    def receipt(self, batch_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
        return ({**dict(row), "counts": json.loads(row["counts_json"]),
                 "errors": json.loads(row["errors_json"])} if row else None)

    def conversations(self, source_id: str | None = None, project_id: str | None = None):
        where = []
        params = []
        if source_id:
            where.append("c.source_id=?")
            params.append(source_id)
        if project_id:
            where.append("c.project_id=?")
            params.append(project_id)
        clause = " AND ".join(where) if where else "1=1"
        with self.connect() as db:
            rows = db.execute(
                f"SELECT c.*,s.provider,s.account_alias,"
                "(SELECT count(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
                f"FROM conversations c JOIN source_instances s ON s.id=c.source_id "
                f"WHERE {clause} ORDER BY c.rowid DESC LIMIT 500", params,
            ).fetchall()
        return [dict(row) for row in rows]

    def messages(self, conversation_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT m.* FROM messages m WHERE m.conversation_id=? ORDER BY m.rowid ASC LIMIT 1000",
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, q: str, project_id: str | None, source_id: str | None) -> list[dict]:
        if not q.strip():
            return []
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        needle = f"%{escaped}%"
        with self.connect() as db:
            rows = db.execute(
                "SELECT m.id AS message_id,m.role,m.content,m.occurred_at,"
                "c.id AS conversation_id,c.title,c.project_id,s.id AS source_id,"
                "s.provider,s.account_alias "
                "FROM message_search f JOIN messages m ON m.id=f.message_id "
                "JOIN conversations c ON c.id=m.conversation_id "
                "JOIN source_instances s ON s.id=c.source_id "
                "WHERE (f.content LIKE ? ESCAPE '\\' OR f.title LIKE ? ESCAPE '\\') "
                "AND (? IS NULL OR c.project_id=?) AND (? IS NULL OR c.source_id=?) "
                "ORDER BY m.rowid DESC LIMIT 100",
                (needle, needle, project_id, project_id, source_id, source_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def projects(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY name").fetchall()
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
