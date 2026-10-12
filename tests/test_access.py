import os

import pytest

from nexus.access import local_access_key
from nexus.api import create_app


@pytest.mark.parametrize("endpoint", ["sources", "conversations", "imports", "projects",
                                      "overview", "search?q=private", "integrity", "connections"])
def test_private_reads_require_the_owner_key(client, endpoint):
    response = client.get("/api/v1/" + endpoint, headers={"Authorization": ""})
    assert response.status_code == 401
    assert client.app.state.access_key not in response.text


def test_wrong_key_cannot_read_or_write(client):
    headers = {"Authorization": "Bearer synthetic-wrong-key-not-a-real-secret"}
    assert client.get("/api/v1/conversations", headers=headers).status_code == 401
    assert client.post("/api/v1/projects", json={"name": "Rejected"}, headers=headers).status_code == 401
    assert client.get("/api/v1/projects").json()["items"] == []


def test_health_does_not_expose_key_or_private_metadata(client):
    response = client.get("/api/v1/health", headers={"Authorization": ""})
    assert response.status_code == 200
    assert client.app.state.access_key not in response.text
    assert "account_alias" not in response.text


def test_key_is_persistent_private_and_not_recreated_on_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    app = create_app(tmp_path / "private" / "nexus.sqlite3")
    key = app.state.access_key
    assert len(key) >= 32
    file = tmp_path / "private" / "nexus-access.key"
    assert file.read_text().strip() == key
    if os.name != "nt":
        assert file.stat().st_mode & 0o777 == 0o600
    assert create_app(tmp_path / "private" / "nexus.sqlite3").state.access_key == key


def test_configured_key_requires_a_strong_token_and_is_not_copied_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "synthetic-test-token-not-a-real-secret")
    app = create_app(tmp_path / "nexus.sqlite3")
    assert app.state.access_key == "synthetic-test-token-not-a-real-secret"
    assert not (tmp_path / "nexus-access.key").exists()
    monkeypatch.setenv("NEXUS_API_TOKEN", "short")
    with pytest.raises(ValueError, match="32-256"):
        create_app(tmp_path / "another.sqlite3")


def test_key_directory_is_rejected_without_changing_permissions(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    path = tmp_path / "nexus-access.key"
    path.mkdir(mode=0o700)
    original_mode = path.stat().st_mode
    with pytest.raises(ValueError, match="file"):
        local_access_key(tmp_path)
    assert path.stat().st_mode == original_mode


@pytest.mark.parametrize("payload", [b"A" * 256 + b" " * 500, b"\xff" * 32],
                         ids=["oversize-padded", "non-ascii"])
def test_invalid_key_file_is_rejected_with_a_generic_error(tmp_path, monkeypatch, payload):
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    path = tmp_path / "nexus-access.key"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="Invalid local access key file"):
        local_access_key(tmp_path)
    assert path.read_bytes() == payload


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n"])
def test_maximum_key_file_accepts_only_the_optional_line_ending(tmp_path, monkeypatch, ending):
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    (tmp_path / "nexus-access.key").write_bytes(b"A" * 256 + ending)
    assert local_access_key(tmp_path) == "A" * 256
