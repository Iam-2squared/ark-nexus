"""Only synthetic uploads; the simulated common TEMP is inside this checkout's test tree."""

import errno
import io
import json
import os
import sqlite3
import tempfile

import pytest
from starlette import formparsers

from nexus.private_storage import PrivateStorageError


def large_fixture():
    return json.dumps({"nexus_fixture": "synthetic-v1", "provider": "chatgpt",
                       "conversations": [{"id": "large", "title": "synthetic marker",
                                          "messages": [
                                              {"id": str(i), "role": "user",
                                               "text": "SYNTHETIC-TEMP-MARKER-" + "x" * 180000}
                                              for i in range(8)]}]}).encode()


@pytest.mark.parametrize("outcome", ["valid", "invalid-json", "dry-run", "invalid-provider",
                                    "invalid-alias", "missing-alias"])
def test_no_multipart_tempfile_even_above_original_spool_threshold(
    client, monkeypatch, tmp_path, outcome,
):
    common = tmp_path / "simulated-common-temp"
    common.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(common))
    before_environment = {k: os.environ.get(k) for k in ("TMP", "TEMP", "TMPDIR")}
    disk_files = []
    original = tempfile.TemporaryFile

    def observed(*args, **kwargs):
        disk_files.append(kwargs.get("dir", tempfile.gettempdir()))
        return original(*args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryFile", observed)
    blob = large_fixture() if outcome != "invalid-json" else b"SYNTHETIC-MARKER-" + b"x" * 1400000
    fields = {"provider": "unknown" if outcome == "invalid-provider" else "chatgpt",
              "account_alias": "/invalid" if outcome == "invalid-alias" else "test"}
    if outcome == "dry-run":
        fields["dry_run"] = "true"
    if outcome == "missing-alias":
        fields.pop("account_alias")
    response = client.post("/api/v1/imports", data=fields,
                           files={"file": ("synthetic.json", blob, "application/json")})
    assert response.status_code == (201 if outcome in {"valid", "dry-run"} else 422)
    assert disk_files == [], "Multipart wrote synthetic plaintext to a disk temporary file"
    assert list(common.iterdir()) == []
    assert tempfile.tempdir == str(common)
    assert {k: os.environ.get(k) for k in before_environment} == before_environment
    if outcome != "valid":
        assert client.get("/api/v1/overview").json()["counts"]["messages"] == 0


@pytest.mark.parametrize("error", [errno.ENOSPC, errno.EROFS, errno.EACCES])
def test_common_temp_unavailable_does_not_break_memory_only_upload(client, monkeypatch, error):
    def refused(*_args, **_kwargs):
        raise OSError(error, "SYNTHETIC-PRIVATE-PATH")

    monkeypatch.setattr(tempfile, "TemporaryFile", refused)
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("synthetic.json", large_fixture(), "application/json")})
    assert response.status_code == 201
    assert response.json()["counts"]["messages_inserted"] == 8


def test_standard_spool_factory_is_never_called(client, monkeypatch):
    def refused(*_args, **_kwargs):
        raise AssertionError("Shared/global spool factory must not be used")

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", refused)
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("synthetic.json", large_fixture(), "application/json")})
    assert response.status_code == 201


def test_every_store_connection_forces_verified_memory_temp(client):
    with client.app.state.store.connect() as db:
        assert db.execute("PRAGMA temp_store").fetchone()[0] == 2
        db.execute("CREATE TEMP TABLE synthetic_sort(value TEXT)")
        db.executemany("INSERT INTO synthetic_sort VALUES (?)", [("合成" + str(i),) for i in range(5000)])
        assert len(db.execute("SELECT value FROM synthetic_sort ORDER BY value DESC").fetchall()) == 5000
        assert db.execute("PRAGMA database_list").fetchall()[1][2] == ""


def test_backup_connections_also_use_memory_temp(client, tmp_path, monkeypatch):
    from nexus import maintenance

    original = sqlite3.connect
    observations = []

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                observations.append(super().execute("PRAGMA temp_store").fetchone()[0])
            return super().execute(sql, *args)

    monkeypatch.setattr(maintenance.sqlite3, "connect",
                        lambda *args, **kwargs: original(*args, factory=Observed, **kwargs))
    maintenance.copy_database(client.app.state.store.path, tmp_path / "copy.sqlite3")
    assert observations == [2, 2]


def test_sqlite_disk_only_build_fails_closed_before_query(client, monkeypatch):
    original = sqlite3.connect

    class DiskOnly(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "PRAGMA compile_options":
                return iter([("TEMP_STORE=0",)])
            return super().execute(sql, *args)

    monkeypatch.setattr(sqlite3, "connect",
                        lambda *args, **kwargs: original(*args, factory=DiskOnly, **kwargs))
    with pytest.raises(PrivateStorageError):
        with client.app.state.store.connect():
            pytest.fail("A disk-only temp build was accepted")


@pytest.mark.parametrize("kind", ["duplicate", "unknown", "incomplete", "invalid-utf8"])
def test_ambiguous_or_incomplete_multipart_is_rejected_without_writes(client, kind):
    boundary = b"nexus-synthetic-boundary"
    body = (b"--" + boundary + b'\r\nContent-Disposition: form-data; name="provider"\r\n\r\nchatgpt\r\n'
            b"--" + boundary + b'\r\nContent-Disposition: form-data; name="account_alias"\r\n\r\ntest\r\n')
    if kind in {"duplicate", "unknown"}:
        name = b"provider" if kind == "duplicate" else b"unsupported"
        body += b"--" + boundary + b'\r\nContent-Disposition: form-data; name="' + name + b'"\r\n\r\nchatgpt\r\n'
    if kind == "invalid-utf8":
        body = body.replace(b"\r\ntest\r\n", b"\r\n\xff\r\n")
    body += (b"--" + boundary + b'\r\nContent-Disposition: form-data; name="file"; filename="synthetic.json"\r\n\r\n'
             + json.dumps({"nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": []}).encode())
    if kind != "incomplete":
        body += b"\r\n--" + boundary + b"--\r\n"
    response = client.post("/api/v1/imports", content=body,
                           headers={"Content-Type": "multipart/form-data; boundary=" + boundary.decode()})
    assert response.status_code == 422
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0
    assert "SYNTHETIC-TEMP-MARKER" not in response.text


def test_exception_in_multipart_handler_closes_memory_buffer(client, monkeypatch):
    buffers = []
    original = formparsers.UploadFile

    def observed(*args, **kwargs):
        buffers.append(kwargs.get("file", args[0] if args else None))
        return original(*args, **kwargs)

    monkeypatch.setattr(formparsers, "UploadFile", observed)
    response = client.post("/api/v1/imports", data={"provider": "unknown", "account_alias": "test"},
                           files={"file": ("synthetic.json", large_fixture(), "application/json")})
    assert response.status_code == 422
    assert buffers and all(file.closed for file in buffers)
    assert all(isinstance(file, io.BytesIO) for file in buffers)
