"""Additive synthetic stress/rollback/copy gates; never use an owner's profile.

These gates supplement the frozen 1,000-message and 30 + 30 search cases.
All generated records deliberately use public synthetic text and new tmp_path files.
"""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from conftest import upload

from nexus import maintenance
from nexus import store as store_module
from nexus.importers import PARSER_VERSION, load_synthetic
from nexus.maintenance import copy_database
from nexus.store import Store

TABLES = (
    "source_instances", "conversations", "messages", "import_batches", "source_events",
    "audit_log", "projects", "message_search", "schema_migrations",
)


def catalog(message_count, per_conversation=100):
    """Our synthetic-v1 contract, not a claimed consumer-provider export schema."""
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    conversations = []
    for first in range(0, message_count, per_conversation):
        conversations.append({
            "id": f"synthetic-c{first // per_conversation:05d}",
            "title": f"Synthetic title {first // per_conversation:05d}",
            "messages": [
                {"id": f"synthetic-m{i:05d}", "role": "user",
                 "text": f"megabatch 日本語 token{i:05d} 100% x_y 🚀",
                 "created_at": (start + timedelta(seconds=i)).isoformat()}
                for i in range(first, min(first + per_conversation, message_count))
            ],
        })
    return {"nexus_fixture": "synthetic-v1", "provider": "chatgpt",
            "conversations": conversations}


def normalized(data):
    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return blob, load_synthetic(blob, "chatgpt")


def import_records(store, data, account="synthetic-megabatch"):
    blob, conversations = normalized(data)
    return store.import_conversations(
        provider="chatgpt", account_alias=account,
        import_hash=hashlib.sha256(blob).hexdigest(),
        parser_version=PARSER_VERSION, conversations=conversations,
    )


def snapshot(store):
    """Logical records, so rollback checks also include FTS/audit/receipt/provenance."""
    with store.connect() as db:
        db.execute("BEGIN")
        return {name: [tuple(row) for row in db.execute(f"SELECT * FROM {name} ORDER BY rowid")]
                for name in TABLES}


def assert_page_walk(fetch, total, key):
    offset = 0
    seen = []
    while True:
        page = fetch(offset)
        assert page["total"] == total
        assert page["offset"] == offset
        assert len(page["items"]) <= page["limit"]
        seen.extend(item[key] for item in page["items"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] == offset + len(page["items"])
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert len(seen) == len(set(seen)) == total
    return seen


def test_10000_message_reimport_and_complete_pagination(client):
    data = catalog(10_000)
    first = upload(client, "chatgpt", data, account="synthetic-stress")
    assert first.status_code == 201
    assert first.json()["counts"]["messages_inserted"] == 10_000
    store = client.app.state.store
    with store.connect() as db:
        original = [tuple(row) for row in db.execute(
            "SELECT id,conversation_id,external_id,content_sha256,occurred_at,observed_at "
            "FROM messages ORDER BY rowid"
        )]
    second = upload(client, "chatgpt", data, account="synthetic-stress")
    assert second.status_code == 201
    assert second.json()["counts"]["messages_inserted"] == 0
    assert second.json()["counts"]["messages_duplicates"] == 10_000
    assert second.json()["source_id"] == first.json()["source_id"]
    with store.connect() as db:
        assert [tuple(row) for row in db.execute(
            "SELECT id,conversation_id,external_id,content_sha256,occurred_at,observed_at "
            "FROM messages ORDER BY rowid"
        )] == original
    assert store.overview()["counts"] == {
        "sources": 1, "conversations": 100, "messages": 10_000, "projects": 0, "imports": 2,
    }
    assert store.integrity_report()["ok"] is True
    conversations = assert_page_walk(
        lambda offset: client.get("/api/v1/conversations", params={
            "limit": 31, "offset": offset}).json(), 100, "external_id",
    )
    assert conversations == [f"synthetic-c{i:05d}" for i in reversed(range(100))]
    hits = assert_page_walk(
        lambda offset: client.get("/api/v1/search", params={
            "q": "日本語", "limit": 100, "offset": offset}).json(),
        10_000, "external_message_id",
    )
    assert hits == [f"synthetic-m{i:05d}" for i in reversed(range(10_000))]
    for query in ("100%", "x_y", "🚀"):
        assert client.get("/api/v1/search", params={"q": query}).json()["total"] == 10_000
    final = client.get("/api/v1/search", params={"q": "日本語", "offset": 10_000}).json()
    assert final["items"] == []
    assert final["total"] == 10_000
    assert final["next_offset"] is None


def test_5000_message_parallel_reimport_is_atomic_and_retryable(tmp_path):
    store = Store(tmp_path / "parallel-synthetic" / "nexus.sqlite3")
    data = catalog(5_000)
    blob, records = normalized(data)

    def run(_):
        return store.import_conversations(
            provider="chatgpt", account_alias="parallel-synthetic",
            import_hash=hashlib.sha256(blob).hexdigest(), parser_version=PARSER_VERSION,
            conversations=records,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(run, range(4)))
    assert sum(receipt["counts"]["messages_inserted"] for receipt in receipts) == 5_000
    assert sum(receipt["counts"]["messages_duplicates"] for receipt in receipts) == 15_000
    assert len({receipt["source_id"] for receipt in receipts}) == 1
    retry = run(None)
    assert retry["counts"]["messages_inserted"] == 0
    assert retry["counts"]["messages_duplicates"] == 5_000
    assert store.overview()["counts"] == {
        "sources": 1, "conversations": 50, "messages": 5_000, "projects": 0, "imports": 5,
    }
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM source_events").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 5
    assert store.integrity_report()["ok"] is True


@pytest.mark.parametrize("field,value", [
    ("text", "SYNTHETIC-CHANGED-BODY"),
    ("role", "assistant"),
    ("created_at", "2026-10-13T00:00:00+00:00"),
])
def test_late_identity_conflict_rolls_back_titles_new_records_receipts_and_fts(
    client, field, value,
):
    data = catalog(300)
    assert upload(client, "chatgpt", data).status_code == 201
    store = client.app.state.store
    before = snapshot(store)
    changed = deepcopy(data)
    for conversation in changed["conversations"]:
        conversation["title"] = "SYNTHETIC-RENAMED-BEFORE-CONFLICT"
        conversation["messages"].insert(0, {
            "id": "new-before-conflict", "role": "user", "text": "SYNTHETIC-ROLLBACK-MARKER",
        })
    changed["conversations"][-1]["messages"][-1][field] = value
    changed["conversations"].insert(0, {
        "id": "new-conversation-before-conflict", "title": "Synthetic new conversation",
        "messages": [{"id": "new", "role": "user", "text": "SYNTHETIC-ROLLBACK-MARKER"}],
    })
    response = upload(client, "chatgpt", changed)
    assert response.status_code == 409
    assert snapshot(store) == before
    assert store.search_page("SYNTHETIC-ROLLBACK-MARKER", None, None)["total"] == 0
    assert store.search_page("SYNTHETIC-RENAMED-BEFORE-CONFLICT", None, None)["total"] == 0
    assert store.integrity_report()["ok"] is True


@pytest.mark.parametrize("failure", [KeyboardInterrupt, sqlite3.OperationalError])
def test_injected_import_interruption_has_zero_partial_writes_and_retry_succeeds(
    tmp_path, monkeypatch, failure,
):
    store = Store(tmp_path / "interrupted-synthetic" / "nexus.sqlite3")
    import_records(store, catalog(10))
    before = snapshot(store)
    real_connect = sqlite3.connect
    insertions = 0

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, sql, *args):
            nonlocal insertions
            if sql.startswith("INSERT INTO messages"):
                insertions += 1
                if insertions == 7:
                    raise failure("synthetic interruption / disk-full simulation")
            return super().execute(sql, *args)

    def interrupted_connect(*args, **kwargs):
        return real_connect(*args, factory=InterruptedConnection, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", interrupted_connect)
        with pytest.raises(failure):
            import_records(store, catalog(50))
    assert snapshot(store) == before
    assert store.integrity_report()["ok"] is True
    retry = import_records(store, catalog(50))
    assert retry["counts"]["messages_inserted"] == 40
    assert retry["counts"]["messages_duplicates"] == 10
    assert store.overview()["counts"]["messages"] == 50
    assert store.overview()["counts"]["imports"] == 2
    assert store.integrity_report()["ok"] is True


def test_timezone_ranges_are_instant_ordered_and_source_representation_preserved(client):
    data = catalog(3)
    stamps = ["2026-10-12T12:30:00+09:00", "2026-10-11T23:00:00-05:00",
              "2026-10-12T03:00:00+00:00"]
    for message, stamp in zip(data["conversations"][0]["messages"], stamps, strict=True):
        message["created_at"] = stamp
    assert upload(client, "chatgpt", data).status_code == 201
    conversation = client.get("/api/v1/conversations").json()["items"][0]
    assert conversation["first_at"] == stamps[2]
    assert conversation["last_at"] == stamps[1]
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()["items"]
    assert [message["occurred_at"] for message in messages] == stamps
    same_instant = deepcopy(data)
    same_instant["conversations"][0]["messages"][0]["created_at"] = "2026-10-12T03:30:00Z"
    before = snapshot(client.app.state.store)
    assert upload(client, "chatgpt", same_instant).status_code == 409
    assert snapshot(client.app.state.store) == before


def test_same_ids_across_accounts_provider_and_project_have_exact_filter_totals(client):
    data = catalog(300)
    sources = []
    for account in ("synthetic-one", "synthetic-two"):
        receipt = upload(client, "chatgpt", data, account=account)
        assert receipt.status_code == 201
        sources.append(receipt.json()["source_id"])
    claude = {"nexus_fixture": "synthetic-v1", "provider": "claude", "chats": [
        {"uuid": conversation["id"], "name": conversation["title"], "messages": [
            {"uuid": message["id"], "sender": "human", "content": message["text"],
             "created_at": message["created_at"]}
            for message in conversation["messages"]
        ]} for conversation in data["conversations"]
    ]}
    receipt = upload(client, "claude", claude, account="synthetic-one")
    assert receipt.status_code == 201
    sources.append(receipt.json()["source_id"])
    project = client.post("/api/v1/projects", json={"name": "Synthetic split project"}).json()
    for source in sources[:2]:
        conversation = client.get("/api/v1/conversations", params={"source_id": source}).json()
        assert conversation["total"] == 3
        assert client.patch("/api/v1/conversations/" + conversation["items"][0]["id"],
                            json={"project_id": project["id"]}).status_code == 200
    assert client.get("/api/v1/search", params={"q": "日本語"}).json()["total"] == 900
    for index, source in enumerate(sources):
        params = {"q": "日本語", "source_id": source, "limit": 37}
        hits = assert_page_walk(
            lambda offset: client.get("/api/v1/search", params={**params, "offset": offset}).json(),
            300, "message_id",
        )
        assert len(hits) == 300
        filtered = client.get("/api/v1/search", params={**params, "project_id": project["id"]})
        assert filtered.json()["total"] == (100 if index < 2 else 0)
    assert client.get("/api/v1/search", params={
        "q": "日本語", "project_id": project["id"]}).json()["total"] == 200
    assert client.app.state.store.integrity_report()["ok"] is True


@pytest.mark.parametrize("column", ["title", "content"])
def test_null_fts_fields_are_corruption_and_cannot_be_copied(tmp_path, column):
    store = Store(tmp_path / "null-synthetic" / "nexus.sqlite3")
    import_records(store, catalog(2))
    with store.connect() as db:
        db.execute(f"UPDATE message_search SET {column}=NULL WHERE rowid=("
                   "SELECT min(rowid) FROM message_search)")
    report = store.integrity_report()
    assert report["ok"] is False
    assert report["checks"]["stale_search_rows"] == 1
    destination = tmp_path / "new-copy" / "nexus.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(store.path, destination)
    assert not destination.exists()


def test_backup_restore_5000_preserves_all_logical_records_and_provenance(tmp_path):
    original = Store(tmp_path / "source-synthetic" / "nexus.sqlite3")
    receipt = import_records(original, catalog(5_000))
    project = original.create_project("Synthetic restored project", None)
    first = original.conversations_page(limit=1)["items"][0]
    original.assign_conversation(first["id"], project["id"])
    before = snapshot(original)
    backup = tmp_path / "new-backup" / "nexus.sqlite3"
    restored = tmp_path / "new-restored" / "nexus.sqlite3"
    copy_database(original.path, backup)
    copy_database(backup, restored)
    store = Store(restored)
    assert snapshot(store) == before
    assert store.integrity_report()["ok"] is True
    assert store.search_page("日本語", project["id"], receipt["source_id"])["total"] == 100
    assert store.search_page("日本語", None, receipt["source_id"])["total"] == 5_000
    assert store.receipt(receipt["id"])["import_hash"] == receipt_hash(catalog(5_000))
    retry = import_records(store, catalog(5_000))
    assert retry["counts"]["messages_inserted"] == 0
    assert retry["counts"]["messages_duplicates"] == 5_000
    assert snapshot(original) == before
    assert Store(backup).overview()["counts"]["imports"] == 1


def receipt_hash(data):
    blob, _ = normalized(data)
    return hashlib.sha256(blob).hexdigest()


def test_backup_wal_snapshot_excludes_uncommitted_changes(tmp_path):
    store = Store(tmp_path / "wal-synthetic" / "nexus.sqlite3")
    import_records(store, catalog(100))
    before = snapshot(store)
    destination = tmp_path / "wal-copy" / "nexus.sqlite3"
    with store.connect() as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE conversations SET title='UNCOMMITTED-SYNTHETIC-TITLE'")
        copy_database(store.path, destination)
        restored = Store(destination)
        assert snapshot(restored) == before
        assert restored.integrity_report()["ok"] is True
        assert restored.search_page("UNCOMMITTED-SYNTHETIC-TITLE", None, None)["total"] == 0
        writer.rollback()
    assert snapshot(store) == before


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_interrupted_backup_closes_connections_removes_only_its_new_destination(
    tmp_path, monkeypatch, interruption,
):
    store = Store(tmp_path / "backup-interrupted-source" / "nexus.sqlite3")
    import_records(store, catalog(100))
    before = snapshot(store)
    untouched = tmp_path / "sentinel"
    untouched.write_bytes(b"synthetic sentinel must remain")
    destination = tmp_path / "backup-interrupted-new" / "nexus.sqlite3"
    real_connect = sqlite3.connect
    opened = []

    class InterruptedReader(sqlite3.Connection):
        def backup(self, writer, *args, **kwargs):
            writer.execute("CREATE TABLE synthetic_partial_copy(marker TEXT)")
            writer.execute("INSERT INTO synthetic_partial_copy VALUES ('SYNTHETIC-PARTIAL')")
            writer.commit()
            raise interruption("synthetic interrupted backup")

    def tracking_connect(*args, **kwargs):
        if not opened:
            kwargs["factory"] = InterruptedReader
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(maintenance.sqlite3, "connect", tracking_connect)
        with pytest.raises(interruption):
            copy_database(store.path, destination)
    assert len(opened) == 2
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    assert not destination.exists()
    assert untouched.read_bytes() == b"synthetic sentinel must remain"
    assert snapshot(store) == before
    copy_database(store.path, destination)
    assert snapshot(Store(destination)) == before


def test_unknown_project_assignment_is_nondestructive_and_reversible(client):
    assert upload(client, "chatgpt", catalog(10)).status_code == 201
    conversation = client.get("/api/v1/conversations").json()["items"][0]
    project = client.post("/api/v1/projects", json={"name": "Synthetic reassignment"}).json()
    path = "/api/v1/conversations/" + conversation["id"]
    assert client.patch(path, json={"project_id": project["id"]}).status_code == 200
    before = snapshot(client.app.state.store)
    assert client.patch(path, json={"project_id": "missing-synthetic-project"}).status_code == 422
    assert snapshot(client.app.state.store) == before
    assert client.patch(path, json={"project_id": None}).status_code == 200
    assert client.get("/api/v1/search", params={
        "q": "日本語", "project_id": project["id"]}).json()["total"] == 0
    assert client.get("/api/v1/projects").json()["items"][0]["conversation_count"] == 0
    assert client.app.state.store.integrity_report()["ok"] is True


def test_additive_migration_failure_is_atomic_and_retry_does_not_reapply_old_versions(
    tmp_path, monkeypatch,
):
    store = Store(tmp_path / "migration-synthetic" / "nexus.sqlite3")
    import_records(store, catalog(100))
    before = snapshot(store)
    fake_package = tmp_path / "synthetic-migrations"
    directory = fake_package / "migrations"
    directory.mkdir(parents=True)
    migration = directory / "0003_synthetic_atomicity.sql"
    migration.write_text(
        "CREATE TABLE synthetic_migration_marker(id INTEGER PRIMARY KEY);\n"
        "INSERT INTO synthetic_migration_marker VALUES(1);\n"
        "INSERT INTO nonexistent_synthetic_table VALUES(1);\n", encoding="utf-8",
    )
    monkeypatch.setattr(store_module.resources, "files", lambda _package: fake_package)
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    assert snapshot(store) == before
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM sqlite_master "
                          "WHERE name='synthetic_migration_marker'").fetchone()[0] == 0
    migration.write_text(
        "CREATE TABLE synthetic_migration_marker(id INTEGER PRIMARY KEY);\n"
        "INSERT INTO synthetic_migration_marker VALUES(1);\n", encoding="utf-8",
    )
    store.migrate()
    store.migrate()
    with store.connect() as db:
        assert [row[0] for row in db.execute(
            "SELECT version FROM schema_migrations ORDER BY version")] == [1, 2, 3]
        assert db.execute("SELECT count(*) FROM synthetic_migration_marker").fetchone()[0] == 1
    after = snapshot(store)
    assert {table: values for table, values in after.items() if table != "schema_migrations"} == {
        table: values for table, values in before.items() if table != "schema_migrations"
    }
    assert after["schema_migrations"][:2] == before["schema_migrations"]
    assert store.integrity_report()["ok"] is True


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_backup_destination_with_existing_sidecar_is_not_touched(tmp_path, suffix):
    store = Store(tmp_path / "sidecar-synthetic-source" / "nexus.sqlite3")
    import_records(store, catalog(100))
    source_before = snapshot(store)
    destination = tmp_path / "new-sidecar-path" / "nexus.sqlite3"
    destination.parent.mkdir(mode=0o700)
    sidecar = destination.with_name(destination.name + suffix)
    sidecar.write_bytes(b"synthetic existing sidecar must remain")
    sidecar.chmod(0o600)
    with pytest.raises(ValueError):
        copy_database(store.path, destination)
    assert not destination.exists()
    assert sidecar.read_bytes() == b"synthetic existing sidecar must remain"
    assert snapshot(store) == source_before
