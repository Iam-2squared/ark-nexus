import os
from pathlib import Path

import pytest
from conftest import upload

from nexus.private_storage import checked_path
from nexus.store import Store


def test_integrity_detects_missing_search_rows_and_bad_hashes(client, seed_chatgpt):
    upload(client, "chatgpt", seed_chatgpt)
    report = client.get("/api/v1/integrity").json()
    assert report["ok"] is True
    with client.app.state.store.connect() as db:
        mid = db.execute("SELECT id FROM messages LIMIT 1").fetchone()[0]
        db.execute("DELETE FROM message_search WHERE message_id=?", (mid,))
        db.execute("UPDATE messages SET content_sha256='bad' WHERE id=?", (mid,))
    report = client.get("/api/v1/integrity").json()
    assert report["ok"] is False
    assert report["checks"]["missing_search_rows"] == 1
    assert report["checks"]["content_hash_mismatches"] == 1
    assert "Plan the ark project" not in str(report)


def test_backup_and_restore_only_to_new_locations(client, seed_chatgpt, tmp_path):
    from nexus.maintenance import copy_database
    upload(client, "chatgpt", seed_chatgpt)
    source = client.app.state.store.path
    backup = tmp_path / "backup" / "nexus.sqlite3"
    restored = tmp_path / "restored" / "nexus.sqlite3"
    copy_database(source, backup)
    copy_database(backup, restored)
    store = Store(restored)
    assert store.overview()["counts"]["messages"] == 2
    assert store.integrity_report()["ok"] is True
    assert len(store.search("ark", None, None)) == 1
    before = backup.read_bytes()
    with pytest.raises(FileExistsError):
        copy_database(source, backup)
    assert backup.read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode check; Windows uses account directory ACLs")
def test_private_database_permissions(tmp_path):
    store = Store(tmp_path / "private" / "nexus.sqlite3")
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.path.parent.stat().st_mode & 0o777 == 0o700


def test_symlink_database_path_does_not_write_to_target(tmp_path):
    target = tmp_path / "target.sqlite3"
    target.write_bytes(b"unchanged")
    link = tmp_path / "linked.sqlite3"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks requires Windows Developer Mode or permissions")
    with pytest.raises(ValueError, match="symlink"):
        Store(link)
    assert target.read_bytes() == b"unchanged"


def test_junction_ancestor_is_rejected_before_any_write(tmp_path, monkeypatch):
    junction = tmp_path / "junction"
    monkeypatch.setattr(Path, "is_junction", lambda self: self == junction)
    with pytest.raises(ValueError, match="junction"):
        checked_path(junction / "nexus.sqlite3")
    assert not junction.exists()


@pytest.mark.skipif(os.name != "nt", reason="Real NTFS junction creation requires Windows")
def test_real_windows_junction_does_not_write_to_target(tmp_path):
    import subprocess
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"unchanged")
    junction = tmp_path / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)],
                            capture_output=True, check=False)
    assert result.returncode == 0, "Unable to create test NTFS junction"
    try:
        with pytest.raises(ValueError, match="junction"):
            Store(junction / "nexus.sqlite3")
        assert sentinel.read_bytes() == b"unchanged"
        assert list(target.iterdir()) == [sentinel]
    finally:
        # Remove only the junction created by this synthetic test, not its target.
        junction.rmdir()


def test_importing_api_module_does_not_create_profile_database(tmp_path):
    import subprocess
    import sys
    env = os.environ.copy()
    directory = tmp_path / "uncreated-profile"
    env["NEXUS_DATA_DIR"] = str(directory)
    result = subprocess.run([sys.executable, "-c", "import nexus.api"], env=env,
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, check=False)
    assert result.returncode == 0
    assert not directory.exists()
