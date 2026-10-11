"""Additive reproductions: never use private profiles or external paths."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import upload

from nexus.maintenance import copy_database
from nexus.store import Store


@pytest.mark.parametrize("name", ["nexus.sqlite3:stream", "NUL.sqlite3", "CON",
                                  "nexus.sqlite3.", "nexus.sqlite3 "])
def test_nonportable_windows_storage_names_rejected_before_creation(tmp_path, name):
    # POSIX can create these literally; Windows may resolve a stream/device/alias instead.
    with pytest.raises(ValueError, match="portable"):
        Store(tmp_path / name)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_database_sidecar_hardlinks_rejected_before_write(tmp_path, suffix):
    target = tmp_path / "sentinel"
    target.write_bytes(b"unchanged")
    sidecar = tmp_path / ("nexus.sqlite3" + suffix)
    os.link(target, sidecar)
    with pytest.raises(ValueError, match="hard link"):
        Store(tmp_path / "nexus.sqlite3")
    assert not (tmp_path / "nexus.sqlite3").exists()
    assert target.read_bytes() == b"unchanged"


def test_database_path_replacement_rechecked_on_each_connection(client, tmp_path):
    store = client.app.state.store
    original = store.path
    original.rename(original.with_suffix(".saved"))
    target = tmp_path / "unrelated.sqlite3"
    target.write_bytes(b"unchanged")
    os.link(target, original)
    response = client.get("/api/v1/overview")
    assert response.status_code == 503
    assert response.json() == {"detail": "Local storage unavailable"}
    assert target.read_bytes() == b"unchanged"


def test_backup_rejects_logically_corrupt_nexus_database(client, seed_chatgpt, tmp_path):
    upload(client, "chatgpt", seed_chatgpt)
    with client.app.state.store.connect() as db:
        db.execute("DELETE FROM message_search")
    destination = tmp_path / "new" / "backup.sqlite3"
    with pytest.raises(ValueError, match="integrity"):
        copy_database(client.app.state.store.path, destination)
    assert not destination.exists()


def test_backup_connections_closed_even_on_failed_copy(client, tmp_path, monkeypatch):
    from nexus import maintenance

    connections = []
    real_connect = sqlite3.connect

    class FailingWriter(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                raise sqlite3.DatabaseError("synthetic failure")
            return super().execute(sql, *args)

    def tracking_connect(*args, **kwargs):
        if len(connections) == 1:
            kwargs["factory"] = FailingWriter
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(maintenance.sqlite3, "connect", tracking_connect)
    destination = tmp_path / "copy.sqlite3"
    with pytest.raises(sqlite3.DatabaseError):
        copy_database(client.app.state.store.path, destination)
    assert len(connections) == 2
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    assert not destination.exists()


def test_backup_cli_errors_do_not_echo_paths_or_tracebacks(tmp_path):
    secret_marker = "PRIVATE-SYNTHETIC-PATH"
    result = subprocess.run(
        [sys.executable, "-m", "nexus.maintenance", str(tmp_path / secret_marker),
         str(tmp_path / "copy.sqlite3")],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert secret_marker not in result.stdout + result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory mode; Windows DACL checked separately")
def test_existing_shared_storage_directory_rejected_without_chmod(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    before = shared.stat().st_mode
    with pytest.raises(ValueError, match="owner-only"):
        Store(shared / "nexus.sqlite3")
    assert shared.stat().st_mode == before
    assert not (shared / "nexus.sqlite3").exists()
