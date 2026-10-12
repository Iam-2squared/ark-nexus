"""Bounded synthetic statement-rollback workloads, never an owner's database.

Native observation is supplied separately. Successful SQL checks do not prove
the location of statement journals, unlink remnants, swap or crash dumps.
"""

import hashlib
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from nexus.importers import Conversation, Message
from nexus.integrity import inspect_integrity
from nexus.maintenance import copy_database
from nexus.private_storage import checked_path, configure_memory_temp
from nexus.store import Store

DEFAULT_ROWS = 2048
MAX_ROWS = 8192
MAX_SECONDS = 20
MAX_DATABASE_BYTES = 128 * 1024 * 1024
TABLES = (
    "source_instances", "import_batches", "projects", "conversations", "messages",
    "source_events", "tasks", "evidence_links", "sync_cursors", "audit_log",
    "message_search", "schema_migrations", "synthetic_statement_rows",
)


class ProbeProblem(ValueError):
    """A fixed diagnostic; exception text and input never enter evidence."""


def require(condition: bool) -> None:
    if not condition:
        raise ProbeProblem("Synthetic SQLite verification failed")


def logical_digest(db: sqlite3.Connection) -> str:
    """Internal comparison only. Evidence contains equality, never row data/hash."""
    digest = hashlib.sha256()
    for table in TABLES:
        digest.update(table.encode("ascii"))
        for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            for value in row:
                data = repr(value).encode("utf-8")
                digest.update(len(data).to_bytes(8, "big"))
                digest.update(data)
    return digest.hexdigest()


def fts_query_counts(db: sqlite3.Connection) -> tuple[int, int]:
    return tuple(db.execute("SELECT count(*) FROM message_search WHERE message_search MATCH ?",
                            (query,)).fetchone()[0]
                 for query in ('"abcdef"', '"Synthetic changed"'))


def seed_database(path: Path, rows: int) -> Store:
    if type(rows) is not int or not 32 <= rows <= MAX_ROWS or path.exists():
        raise ProbeProblem("A new bounded synthetic SQLite database is required")
    store = Store(path)
    messages = []
    for index in range(rows):
        text = "Synthetic SQLite 日本語 " + str(index) + " abcdef" * 64
        messages.append(Message(
            f"synthetic-message-{index}", "user", text, None,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        ))
    store.import_conversations(
        provider="chatgpt", account_alias="synthetic-statement-probe",
        import_hash="0" * 64, parser_version="synthetic-statement-probe-v1",
        conversations=[Conversation("synthetic-conversation", "Synthetic original", messages)],
    )
    with store.connect() as db:
        db.execute("CREATE TABLE synthetic_statement_rows ("
                   "ordinal INTEGER PRIMARY KEY, unique_value TEXT NOT NULL UNIQUE, "
                   "amount INTEGER NOT NULL CHECK(amount>=0), payload TEXT NOT NULL, "
                   "message_ref TEXT NOT NULL REFERENCES messages(id))")
        ids = [row[0] for row in db.execute("SELECT id FROM messages ORDER BY rowid")]
        db.executemany("INSERT INTO synthetic_statement_rows VALUES(?,?,?,?,?)", [
            (index, f"unique-{index}", 0, "Synthetic payload " + "abcdef" * 80, identity)
            for index, identity in enumerate(ids)
        ])
    return store


def run_statements(db: sqlite3.Connection, rows: int, journal_mode: str,
                   *, temp_store: str = "memory") -> dict:
    """A failed statement must preserve earlier writes in its open transaction."""
    require(type(rows) is int and 32 <= rows <= MAX_ROWS)
    require(journal_mode in ("delete", "wal"))
    configure_memory_temp(db)
    require(temp_store in ("memory", "file"))
    if temp_store == "file":
        # Only an explicit synthetic positive control, never Store or production.
        db.execute("PRAGMA temp_store=FILE")
        require(db.execute("PRAGMA temp_store").fetchone()[0] == 1)
    require(db.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0] == journal_mode)
    require(db.execute("PRAGMA synchronous").fetchone()[0] >= 1)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA cache_size=16")
    page_size = db.execute("PRAGMA page_size").fetchone()[0]
    require(type(page_size) is int and 512 <= page_size <= 65536
            and page_size & (page_size - 1) == 0)
    maximum_pages = MAX_DATABASE_BYTES // page_size
    require(db.execute(f"PRAGMA max_page_count={maximum_pages}").fetchone()[0] == maximum_pages)
    db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2 * 1024 * 1024)
    deadline = time.monotonic() + MAX_SECONDS
    db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    touched = [0]

    def tick():
        touched[0] += 1
        return 0

    db.create_function("nexus_synthetic_tick", 0, tick)
    db.executescript("""
        CREATE TEMP TRIGGER synthetic_seen_insert AFTER INSERT ON synthetic_statement_rows
        BEGIN SELECT nexus_synthetic_tick(); END;
        CREATE TEMP TRIGGER synthetic_seen_update AFTER UPDATE ON synthetic_statement_rows
        BEGIN SELECT nexus_synthetic_tick(); END;
        CREATE TEMP TRIGGER synthetic_seen_message AFTER UPDATE OF content ON messages
        BEGIN SELECT nexus_synthetic_tick(); END;
    """)
    db.execute("CREATE TEMP TRIGGER synthetic_late_abort BEFORE UPDATE OF content ON messages "
               "WHEN old.external_id=? BEGIN SELECT RAISE(ABORT,'Synthetic statement abort'); END"
               .replace("?", "'synthetic-message-" + str(rows - 1) + "'"))
    statements = {
        "late_unique_insert": (
            "INSERT INTO synthetic_statement_rows "
            "SELECT ordinal+?, CASE WHEN ordinal=? THEN 'unique-0' "
            "ELSE 'inserted-'||ordinal END, amount,payload,message_ref "
            "FROM synthetic_statement_rows ORDER BY ordinal", (rows, rows - 1),
        ),
        "late_check_update": (
            "UPDATE synthetic_statement_rows SET "
            "amount=CASE WHEN ordinal=? THEN -1 ELSE amount+1 END, "
            "payload=payload||' Synthetic changed'", (rows - 1,),
        ),
        "late_trigger_fts_update": (
            "UPDATE messages SET content=?,content_sha256=?",
            ("Synthetic changed 日本語 " * 32,
             hashlib.sha256(("Synthetic changed 日本語 " * 32).encode("utf-8")).hexdigest()),
        ),
    }
    outcomes = []
    try:
        for kind, (statement, parameters) in statements.items():
            touched[0] = 0
            db.execute("BEGIN IMMEDIATE")
            identity = "synthetic-prior-" + journal_mode + "-" + kind
            db.execute("INSERT INTO projects(id,name) VALUES(?,?)", (identity, "Synthetic prior"))
            before = logical_digest(db)
            require(fts_query_counts(db) == (rows, 0))
            try:
                db.execute(statement, parameters)
            except sqlite3.IntegrityError:
                pass
            else:
                raise ProbeProblem("Synthetic SQLite verification failed")
            require(touched[0] == rows - 1)
            require(db.in_transaction and logical_digest(db) == before)
            require(db.execute("SELECT count(*) FROM projects WHERE id=?", (identity,))
                    .fetchone()[0] == 1)
            require(inspect_integrity(db)["ok"])
            require(fts_query_counts(db) == (rows, 0))
            db.execute("INSERT INTO message_search(message_search) VALUES('integrity-check')")
            db.commit()
            outcomes.append({"case": kind, "partial_row_callbacks": touched[0],
                             "statement_rollback": True, "prior_transaction_write_retained": True,
                             "stored_integrity": True, "fts_query_equal": True,
                             "fts_internal_integrity": True})
        # Cancellation is different: SQLite interrupts may roll back the whole transaction.
        before = logical_digest(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO projects(id,name) VALUES('synthetic-cancel','Synthetic cancel')")
        db.set_progress_handler(lambda: 1, 1)
        try:
            db.execute("UPDATE synthetic_statement_rows SET payload=payload||' interrupted'")
        except sqlite3.OperationalError:
            pass
        else:
            raise ProbeProblem("Synthetic SQLite verification failed")
        finally:
            db.set_progress_handler(None, 0)
            db.rollback()
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        require(logical_digest(db) == before and inspect_integrity(db)["ok"])
        db.execute("CREATE TEMP TABLE synthetic_materialization(value TEXT NOT NULL)")
        db.executemany("INSERT INTO synthetic_materialization VALUES(?)", [
            ("Synthetic sort " + str(index) + " abcdef" * 64,) for index in range(rows)
        ])
        materialized = db.execute(
            "SELECT count(*) FROM (SELECT DISTINCT value FROM synthetic_materialization "
            "ORDER BY value DESC LIMIT ?)", (rows,),
        ).fetchone()[0]
        db.commit()
        expected_temp = 2 if temp_store == "memory" else 1
        require(materialized == rows
                and db.execute("PRAGMA temp_store").fetchone()[0] == expected_temp)
        return {"rows": rows, "journal_mode": journal_mode, "cache_pages": 16,
                "page_size": page_size, "max_database_bytes": MAX_DATABASE_BYTES,
                "temp_store": expected_temp, "cases": outcomes,
                "interrupted_transaction_rollback": True,
                "temp_sort_rows": materialized, "native_capture_claimed": False}
    finally:
        db.set_progress_handler(None, 0)


def run_workload(root: Path, *, rows: int = DEFAULT_ROWS, connection_factory=sqlite3.connect,
                 before_case=None, temp_store: str = "memory") -> dict:
    root = checked_path(root)
    if root.exists() or type(rows) is not int or not 32 <= rows <= MAX_ROWS:
        raise ProbeProblem("A new bounded synthetic SQLite directory is required")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    reports = []
    for mode in ("delete", "wal"):
        store = seed_database(root / mode / "synthetic.sqlite3", rows)
        if before_case is not None:
            before_case(mode)
        with closing(connection_factory(store.path)) as db:
            report = run_statements(db, rows, mode, temp_store=temp_store)
            original = logical_digest(db)
        # Backup/restore use the real safe copy code, independently of the VFS capture scope.
        backup = root / (mode + "-backup") / "synthetic.sqlite3"
        restored = root / (mode + "-restored") / "synthetic.sqlite3"
        copy_database(store.path, backup)
        copy_database(backup, restored)
        with Store(restored).connect() as copy:
            report["backup_restore_logical_equal"] = logical_digest(copy) == original
            require(report["backup_restore_logical_equal"] and inspect_integrity(copy)["ok"])
            require(fts_query_counts(copy) == (rows, 0))
            copy.execute("INSERT INTO message_search(message_search) VALUES('integrity-check')")
            report["restored_fts_query_equal"] = True
        reports.append(report)
    return {"status": "synthetic_PASS", "workloads": reports,
            "storage_location_qualified": False, "private_import_allowed": False}
