"""Fail-closed database guards on new synthetic files, never retained evidence."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from copy import deepcopy
from pathlib import Path

import pytest
from conftest import upload

from nexus import maintenance
from nexus import store as store_module
from nexus.integrity import inspect_integrity
from nexus.maintenance import copy_database
from nexus.private_storage import PrivateStorageError
from nexus.store import Store


def readonly_counts(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("source_instances", "conversations", "messages", "import_batches",
                              "source_events", "audit_log", "message_search")}


def corrupt(path, statement):
    # This independent, synthetic writer intentionally defaults FK enforcement
    # off. Store must detect the damage instead of adding another successful batch.
    with closing(sqlite3.connect(path)) as db:
        db.execute(statement)
        db.commit()


@pytest.mark.parametrize("operation", ["search", "empty_search", "overview", "sources",
                                       "imports", "conversations", "messages", "receipt",
                                       "projects", "project_create", "project_assign", "import"])
def test_public_operations_refuse_foreign_key_corruption_without_new_writes(
    client, seed_chatgpt, operation,
):
    receipt = upload(client, "chatgpt", seed_chatgpt).json()
    conversation = client.get("/api/v1/conversations").json()["items"][0]
    path = client.app.state.store.path
    corrupt(path, "UPDATE messages SET conversation_id='synthetic-missing-conversation'")
    before = readonly_counts(path)
    if operation == "import":
        result = upload(client, "chatgpt", seed_chatgpt)
    elif operation == "project_create":
        result = client.post("/api/v1/projects", json={"name": "Synthetic blocked project"})
    elif operation == "project_assign":
        result = client.patch("/api/v1/conversations/" + conversation["id"],
                              json={"project_id": None})
    else:
        paths = {
            "search": "/api/v1/search?q=ark", "empty_search": "/api/v1/search?q=%20",
            "overview": "/api/v1/overview", "sources": "/api/v1/sources",
            "imports": "/api/v1/imports", "conversations": "/api/v1/conversations",
            "messages": "/api/v1/conversations/" + conversation["id"] + "/messages",
            "receipt": "/api/v1/imports/" + receipt["id"], "projects": "/api/v1/projects",
        }
        result = client.get(paths[operation])
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    assert readonly_counts(path) == before
    report = client.get("/api/v1/integrity").json()
    assert report["ok"] is False
    assert report["checks"]["foreign_key_errors"] == 2


@pytest.mark.parametrize("statement,check", [
    ("UPDATE source_events SET external_event_key='import:synthetic-missing-batch'",
     "orphan_import_events"),
    ("UPDATE source_events SET raw_ref='synthetic-mismatched-hash'", "orphan_import_events"),
    ("UPDATE source_events SET source_id=NULL", "orphan_import_events"),
    ("UPDATE audit_log SET target='synthetic-missing-batch'", "orphan_import_audits"),
    ("DELETE FROM source_events", "missing_import_events"),
    ("DELETE FROM audit_log", "missing_import_audits"),
    ("UPDATE import_batches SET source_id=NULL", "orphan_import_batches"),
    ("UPDATE import_batches SET ended_at=NULL", "incomplete_import_batches"),
])
def test_import_provenance_without_fk_constraint_is_detected_and_refused(
    client, seed_chatgpt, tmp_path, statement, check,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    corrupt(store.path, statement)
    before = readonly_counts(store.path)
    report = store.integrity_report()
    assert report["ok"] is False
    assert report["checks"][check] == 1
    assert report["checks"]["foreign_key_errors"] == 0
    result = client.get("/api/v1/search", params={"q": "ark"})
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    result = upload(client, "chatgpt", seed_chatgpt)
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    destination = tmp_path / "new-corrupt-copy" / "nexus.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(store.path, destination)
    assert not destination.exists()
    assert readonly_counts(store.path) == before


def test_internal_fts_postings_mismatch_is_counted_without_source_writes(
    client, seed_chatgpt, tmp_path,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    # Keep message/hash and logical FTS content equal while leaving the old
    # postings in place. Existing logical-row checks cannot see this condition.
    with store.connect() as db:
        row = db.execute("SELECT id FROM messages ORDER BY rowid LIMIT 1").fetchone()[0]
        value = "Synthetic replacement token uniqueguard"
        db.execute("DROP TRIGGER messages_fts_au")
        db.execute("UPDATE messages SET content=?,content_sha256=? WHERE id=?",
                   (value, hashlib.sha256(value.encode()).hexdigest(), row))
        db.execute("UPDATE message_search_content SET c2=? WHERE c0=?", (value, row))
    before = store.path.read_bytes()
    with closing(sqlite3.connect(store.path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        assert db.execute("SELECT count(*) FROM message_search WHERE message_search "
                          "MATCH 'uniqueguard'").fetchone()[0] == 0
    report = store.integrity_report()
    assert report["ok"] is False
    assert report["checks"]["fts_index_errors"] == 1
    assert report["checks"]["stale_search_rows"] == 0
    assert report["checks"]["content_hash_mismatches"] == 0
    assert store.path.read_bytes() == before
    destination = tmp_path / "new-postings-copy" / "nexus.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(store.path, destination)
    assert not destination.exists()
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("operation", ["overview", "import", "raw_connection"])
def test_store_refuses_substituted_regular_database_before_access(
    client, seed_chatgpt, tmp_path, operation,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    alternate = Store(tmp_path / "synthetic-alternate" / "nexus.sqlite3")
    original = store.path.with_name("synthetic-original-held.sqlite3")
    store.path.rename(original)
    alternate.path.rename(store.path)
    original_before = original.read_bytes()
    replacement_before = store.path.read_bytes()
    if operation == "raw_connection":
        with pytest.raises(PrivateStorageError):
            with store.connect():
                pytest.fail("A different regular database identity was accepted")
    else:
        result = (upload(client, "chatgpt", seed_chatgpt) if operation == "import"
                  else client.get("/api/v1/overview"))
        assert result.status_code == 503
        assert result.json() == {"detail": "Local storage unavailable"}
    assert original.read_bytes() == original_before
    assert store.path.read_bytes() == replacement_before


def test_absent_bound_database_is_not_implicitly_recreated(client):
    store = client.app.state.store
    held = store.path.with_name("synthetic-created-held.sqlite3")
    store.path.rename(held)
    before = held.read_bytes()
    result = client.get("/api/v1/overview")
    assert result.status_code == 503
    assert not store.path.exists()
    assert held.read_bytes() == before


@pytest.mark.parametrize("interruption", [sqlite3.OperationalError, KeyboardInterrupt])
def test_commit_failure_rolls_back_receipt_fts_and_provenance_then_retry_is_idempotent(
    client, seed_chatgpt, monkeypatch, interruption,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    before = readonly_counts(store.path)
    changed = deepcopy(seed_chatgpt)
    changed["conversations"][0]["messages"].append(
        {"id": "synthetic-next", "role": "user", "text": "Synthetic next record"})
    blob = json.dumps(changed).encode()
    real_connect = sqlite3.connect
    connections = []

    class FailedCommit(sqlite3.Connection):
        def commit(self):
            raise interruption("Synthetic secret/path/key must not become an API diagnostic")

    def observed(*args, **kwargs):
        connection = real_connect(*args, factory=FailedCommit, **kwargs)
        connections.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(store_module.sqlite3, "connect", observed)
        with pytest.raises(interruption):
            from nexus.importers import PARSER_VERSION, load_synthetic
            store.import_conversations(provider="chatgpt", account_alias="personal",
                                       import_hash=hashlib.sha256(blob).hexdigest(),
                                       parser_version=PARSER_VERSION,
                                       conversations=load_synthetic(blob, "chatgpt"))
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    assert readonly_counts(store.path) == before
    result = upload(client, "chatgpt", changed)
    assert result.status_code == 201
    assert result.json()["counts"]["messages_inserted"] == 1
    assert upload(client, "chatgpt", changed).json()["counts"]["messages_inserted"] == 0
    assert store.integrity_report()["ok"] is True


def test_backup_refuses_replaced_source_identity_after_open(
    client, seed_chatgpt, tmp_path, monkeypatch,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    source = client.app.state.store.path
    replacement = Store(tmp_path / "synthetic-copy-alternate" / "nexus.sqlite3")
    held = source.with_name("synthetic-copy-source-held.sqlite3")
    destination = tmp_path / "new-replaced-source-copy" / "nexus.sqlite3"
    real_connect = sqlite3.connect
    opened = []

    def replaced_after_open(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        if not opened:
            # Close first, so Windows too can perform the controlled replacement.
            connection.close()
            source.rename(held)
            replacement.path.rename(source)
            connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(maintenance.sqlite3, "connect", replaced_after_open)
        with pytest.raises(PrivateStorageError):
            copy_database(source, destination)
    assert not destination.exists()
    assert readonly_counts(source)["messages"] == 0
    assert readonly_counts(held)["messages"] == 2
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_store_refuses_changed_parent_even_when_main_identity_is_preserved(client):
    store = client.app.state.store
    directory = store.path.parent
    held_directory = directory.with_name(directory.name + "-synthetic-held")
    identity = store.path.stat().st_dev, store.path.stat().st_ino
    directory.rename(held_directory)
    directory.mkdir(mode=0o700)
    (held_directory / store.path.name).rename(store.path)
    assert (store.path.stat().st_dev, store.path.stat().st_ino) == identity
    result = client.get("/api/v1/overview")
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}


def test_reference_check_and_page_share_one_wal_snapshot(client, seed_chatgpt, monkeypatch):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    with store.connect() as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    original = store_module.require_references
    changed = False

    def corrupt_after_approved_snapshot(db):
        nonlocal changed
        original(db)
        if not changed:
            corrupt(store.path, "DELETE FROM audit_log")
            changed = True

    with monkeypatch.context() as patch:
        patch.setattr(store_module, "require_references", corrupt_after_approved_snapshot)
        page = client.get("/api/v1/search", params={"q": "ark"})
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert changed is True
    # The prior request used its validated old snapshot. The next sees and
    # refuses the independently committed damage; it does not silently repair it.
    refused = client.get("/api/v1/search", params={"q": "ark"})
    assert refused.status_code == 503
    assert refused.json() == {"detail": "Local storage unavailable"}
    assert readonly_counts(store.path)["audit_log"] == 0


def test_foreign_keys_must_be_observed_enabled_before_connection_is_yielded(
    client, monkeypatch,
):
    real_connect = sqlite3.connect
    connections = []

    class IgnoredForeignKeys(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "PRAGMA foreign_keys=ON":
                return super().execute("SELECT 1")
            return super().execute(sql, *args)

    def ignored(*args, **kwargs):
        # The API worker creates this synthetic connection. Allow only this
        # test's observer to verify closure from the test thread afterwards.
        kwargs["check_same_thread"] = False
        connection = real_connect(*args, factory=IgnoredForeignKeys, **kwargs)
        connections.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(store_module.sqlite3, "connect", ignored)
        result = client.get("/api/v1/overview")
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_read_only_integrity_has_no_source_write_authorizations(client, seed_chatgpt):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    before = store.path.read_bytes()
    writes = []

    def reject_source_writes(action, *_args):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                      sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_TEMP_TABLE,
                      sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_TEMP_TABLE):
            writes.append(action)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    with closing(sqlite3.connect(store.path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        db.set_authorizer(reject_source_writes)
        assert inspect_integrity(db)["ok"] is True
        assert db.total_changes == 0
    assert writes == []
    assert store.path.read_bytes() == before


def test_page_requests_do_not_copy_fts_or_hash_the_entire_database(
    client, seed_chatgpt, monkeypatch,
):
    from nexus import integrity

    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201

    def unavailable(*_args):
        pytest.fail("A page request invoked the explicit deep integrity scan")

    monkeypatch.setattr(integrity, "_fts_index_errors", unavailable)
    monkeypatch.setattr(integrity, "_content_hash_matches", unavailable)
    for path in ("/api/v1/search?q=ark", "/api/v1/conversations", "/api/v1/imports",
                 "/api/v1/overview", "/api/v1/projects", "/api/v1/sources"):
        assert client.get(path).status_code == 200


def test_failed_backup_does_not_remove_a_newly_shared_destination_identity(
    client, tmp_path, monkeypatch,
):
    source = client.app.state.store.path
    destination = tmp_path / "new-shared-destination" / "nexus.sqlite3"
    alias = tmp_path / "synthetic-shared-alias.sqlite3"
    real_connect = sqlite3.connect
    opened = []

    class InterruptedReader(sqlite3.Connection):
        def backup(self, writer, *_args, **_kwargs):
            raise KeyboardInterrupt("Synthetic interruption")

    class SharingWriter(sqlite3.Connection):
        def close(self):
            super().close()
            os.link(destination, alias)

    def tracked(*args, **kwargs):
        connection = real_connect(*args, factory=InterruptedReader if not opened
                                  else SharingWriter, **kwargs)
        opened.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(maintenance.sqlite3, "connect", tracked)
        with pytest.raises(KeyboardInterrupt):
            copy_database(source, destination)
    assert destination.is_file()
    assert alias.is_file()
    assert destination.stat().st_nlink == 2
    assert destination.stat().st_ino == alias.stat().st_ino


@pytest.mark.parametrize("target", ["main", "directory"])
def test_unavailable_file_identity_is_refused(tmp_path, monkeypatch, target):
    path = tmp_path / "synthetic-unknown-identity" / "nexus.sqlite3"
    observed_path = path if target == "main" else path.parent
    original_stat = Path.stat

    class UnknownIdentity:
        st_ino = 0

        def __init__(self, original):
            self.original = original

        def __getattr__(self, name):
            return getattr(self.original, name)

    def unknown_stat(self, *args, **kwargs):
        original = original_stat(self, *args, **kwargs)
        return UnknownIdentity(original) if self == observed_path else original

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", unknown_stat)
        with pytest.raises(PrivateStorageError, match="identity"):
            Store(path)


def test_oversized_fts_value_is_refused_before_copying_into_python(
    client, seed_chatgpt, monkeypatch,
):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    store = client.app.state.store
    corrupt(store.path, "UPDATE message_search_content SET c2=zeroblob(2097153) "
            "WHERE id=(SELECT min(id) FROM message_search_content)")
    before = store.path.read_bytes()
    real_connect = sqlite3.connect
    attempted = []

    class RefuseOversizedPythonCopy(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "SELECT * FROM message_search_content":
                attempted.append(True)
                raise AssertionError("Oversized value reached the Python inspection copy")
            return super().execute(sql, *args)

    with monkeypatch.context() as patch:
        patch.setattr(store_module.sqlite3, "connect", lambda *args, **kwargs:
                      real_connect(*args, factory=RefuseOversizedPythonCopy, **kwargs))
        result = client.get("/api/v1/integrity")
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    assert attempted == []
    assert store.path.read_bytes() == before


def test_deep_fts_copy_byte_budget_is_fail_closed(client, seed_chatgpt, monkeypatch):
    from nexus import integrity

    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    before = client.app.state.store.path.read_bytes()
    # Exercise the finite copy budget with a small synthetic dataset rather than
    # creating a 128+ MiB DB solely to consume the public runner's resources.
    monkeypatch.setattr(integrity, "MAX_FTS_INSPECTION_BYTES", 1, raising=False)
    result = client.get("/api/v1/integrity")
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    assert client.app.state.store.path.read_bytes() == before


def test_deep_fts_deadline_is_failure_not_success(client, seed_chatgpt, monkeypatch):
    from nexus import integrity

    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    before = client.app.state.store.path.read_bytes()
    clocks = iter((0.0, 11.0))
    monkeypatch.setattr(integrity, "_clock", lambda: next(clocks, 11.0), raising=False)
    result = client.get("/api/v1/integrity")
    assert result.status_code == 503
    assert result.json() == {"detail": "Local storage unavailable"}
    assert client.app.state.store.path.read_bytes() == before
