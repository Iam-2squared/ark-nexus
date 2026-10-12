"""Additional stored-record corruption gates using new synthetic databases only."""

import json
import os
import sqlite3

import pytest
from conftest import upload

from nexus import maintenance
from nexus.maintenance import copy_database
from nexus.store import Store


@pytest.mark.parametrize("table,columns,values", [
    ("source_instances", "provider,product,account_alias",
     ("chatgpt", "consumer_chat", "synthetic-invalid-identity")),
    ("projects", "name", ("Synthetic invalid identity",)),
    ("tasks", "title", ("Synthetic invalid identity",)),
])
@pytest.mark.parametrize("invalid_id", [None, "", "synthetic\x00identity",
                                       sqlite3.Binary(b"synthetic-identity")])
def test_invalid_primary_key_is_counted_and_backup_is_refused(
    tmp_path, table, columns, values, invalid_id,
):
    # SQLite's ordinary TEXT PRIMARY KEY accepts NULL and BLOB values. These
    # rows can satisfy SQLite/FK integrity while violating Nexus's string IDs.
    store = Store(tmp_path / "invalid-synthetic-identity" / "nexus.sqlite3")
    with store.connect() as db:
        db.execute(f"INSERT INTO {table}(id,{columns}) VALUES "
                   f"({','.join('?' for _ in range(len(values) + 1))})",
                   (invalid_id, *values))
    report = store.integrity_report()
    assert report["ok"] is False
    assert report["checks"]["invalid_primary_keys"] == 1
    assert report["checks"]["sqlite_errors"] == 0
    assert report["checks"]["foreign_key_errors"] == 0
    destination = tmp_path / "new-copy" / "nexus.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(store.path, destination)
    assert not destination.exists()
    with store.connect() as db:
        assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1


@pytest.mark.parametrize("content", [b"synthetic BLOB content", b"\xff\xfe\x00"])
def test_blob_content_returns_counts_without_exception_or_private_value(
    client, seed_chatgpt, tmp_path, content,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    with client.app.state.store.connect() as db:
        db.execute("UPDATE messages SET content=? WHERE external_id='msg-1'",
                   (sqlite3.Binary(content),))
    response = client.get("/api/v1/integrity")
    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is False
    assert report["checks"]["content_hash_mismatches"] == 1
    assert all(type(value) is int and value >= 0 for value in report["checks"].values())
    serialized = json.dumps(report)
    assert "BLOB content" not in serialized
    assert str(tmp_path) not in serialized
    destination = tmp_path / "new-invalid-content-copy" / "nexus.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(client.app.state.store.path, destination)
    assert not destination.exists()


def test_blob_hash_is_rejected_even_when_its_bytes_spell_a_valid_digest(
    client, seed_chatgpt,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    with client.app.state.store.connect() as db:
        db.execute("UPDATE messages SET content_sha256=CAST(content_sha256 AS BLOB) "
                   "WHERE external_id='msg-1'")
    report = client.app.state.store.integrity_report()
    assert report["ok"] is False
    assert report["checks"]["content_hash_mismatches"] == 1


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("replacement_kind", ["new_file", "hardlink"])
def test_interrupted_copy_preserves_a_replaced_destination_identity(
    client, seed_chatgpt, tmp_path, monkeypatch, interruption, replacement_kind,
):
    # Replacement happens only after the writer closes, so this checks the
    # identity guard on Windows too without racing another user or process.
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    source_before = store.path.read_bytes()
    destination = tmp_path / "new-identity-copy" / "nexus.sqlite3"
    held_copy = destination.with_name("created-copy-held.sqlite3")
    sentinel = tmp_path / "synthetic-replacement-sentinel"
    marker = b"Synthetic existing destination identity must remain"
    sentinel.write_bytes(marker)
    sentinel.chmod(0o600)
    real_connect = sqlite3.connect
    opened = []

    class InterruptedReader(sqlite3.Connection):
        def backup(self, writer, *args, **kwargs):
            writer.execute("CREATE TABLE synthetic_partial_copy(id INTEGER)")
            writer.commit()
            raise interruption("Synthetic copy interruption")

    class ReplacingWriter(sqlite3.Connection):
        def close(self):
            super().close()
            destination.rename(held_copy)
            if replacement_kind == "hardlink":
                os.link(sentinel, destination)
            else:
                destination.write_bytes(marker)
                destination.chmod(0o600)

    def tracking_connect(*args, **kwargs):
        kwargs["factory"] = InterruptedReader if not opened else ReplacingWriter
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(maintenance.sqlite3, "connect", tracking_connect)
        with pytest.raises(interruption):
            copy_database(store.path, destination)
    assert destination.read_bytes() == marker
    assert sentinel.read_bytes() == marker
    assert held_copy.is_file()
    assert store.path.read_bytes() == source_before
    assert len(opened) == 2
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_backup_restore_preserves_reserved_tables_without_enabling_execution(
    client, seed_chatgpt, tmp_path,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    source = client.app.state.store
    tables = ("source_instances", "conversations", "messages", "import_batches",
              "source_events", "audit_log", "projects", "tasks", "evidence_links",
              "sync_cursors", "message_search", "schema_migrations")
    with source.connect() as db:
        source_id = db.execute("SELECT id FROM source_instances").fetchone()[0]
        event_id = db.execute("SELECT id FROM source_events").fetchone()[0]
        db.execute("INSERT INTO tasks(id,title) VALUES(?,?)",
                   ("synthetic-reserved-task", "Synthetic proposed task; no execution"))
        db.execute("INSERT INTO evidence_links(id,entity_type,entity_id,source_event_id) "
                   "VALUES(?,?,?,?)", ("synthetic-reserved-evidence", "task",
                                        "synthetic-reserved-task", event_id))
        db.execute("INSERT INTO sync_cursors(source_id,adapter_version,cursor) VALUES(?,?,?)",
                   (source_id, "synthetic-disabled-v1", "synthetic-opaque-cursor"))
        before = {table: [tuple(row) for row in db.execute(
            f"SELECT * FROM {table} ORDER BY rowid")] for table in tables}
    backup = tmp_path / "reserved-new-backup" / "nexus.sqlite3"
    restored = tmp_path / "reserved-new-restored" / "nexus.sqlite3"
    copy_database(source.path, backup)
    copy_database(backup, restored)
    result = Store(restored)
    with result.connect() as db:
        after = {table: [tuple(row) for row in db.execute(
            f"SELECT * FROM {table} ORDER BY rowid")] for table in tables}
    assert after == before
    assert result.integrity_report()["ok"] is True
    assert result.overview()["external_providers_connected"] is False
    assert all(item["capabilities"]["dispatch_new"] is False for item in result.sources())
