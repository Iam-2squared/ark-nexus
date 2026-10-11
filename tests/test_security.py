import asyncio
import io
import json
import stat
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from nexus.api import create_app


@pytest.mark.parametrize("host", ["attacker.invalid:8788", "127.0.0.1.attacker.invalid:8788",
                                  "localhost:9999", "127.0.0.1:8788@attacker.invalid"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_host_rebinding_blocked(client, host, method):
    path = "/api/v1/health" if method == "GET" else "/api/v1/projects"
    r = client.request(method, path, headers={"Host": host}, json={"name": "Rejected"})
    assert r.status_code == 403
    assert client.get("/api/v1/projects").json()["items"] == []


@pytest.mark.parametrize("origin", ["https://attacker.invalid", "null", "http://localhost:9999"])
def test_foreign_origin_reads_blocked(client, origin):
    assert client.get("/api/v1/sources", headers={"Origin": origin}).status_code == 403


def test_cross_site_without_origin_blocked(client):
    assert client.get("/api/v1/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_write_needs_non_simple_header(client):
    r = client.post("/api/v1/projects", json={"name": "Rejected"},
                    headers={"X-Nexus-Request": ""})
    assert r.status_code == 403
    assert client.get("/api/v1/projects").json()["items"] == []


def test_non_loopback_peer_blocked(tmp_path):
    with TestClient(create_app(tmp_path / "nexus.sqlite3"),
                    base_url="http://127.0.0.1:8788", client=("192.0.2.1", 1)) as c:
        assert c.get("/api/v1/health").status_code == 403


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://localhost:5173"])
def test_dashboard_proxy_writes_work(client, origin):
    r = client.post("/api/v1/projects", json={"name": "Allowed"}, headers={"Origin": origin})
    assert r.status_code == 201


def test_body_size_checked_before_json_or_multipart_parsing(client):
    r = client.post("/api/v1/projects", content=b"x", headers={"Content-Length": "1000000"})
    assert r.status_code == 413
    r = client.post("/api/v1/imports", content=b"x",
                    headers={"Content-Length": str(10 * 1024 * 1024)})
    assert r.status_code == 413


def test_chunked_body_is_bounded(client):
    async def check():
        async def chunks():
            for _ in range(70):
                yield b"x" * 1024
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="http://127.0.0.1:8788"
        ) as c:
            return await c.post("/api/v1/projects", content=chunks(),
                                headers={"X-Nexus-Request": "1", "Content-Type": "application/json",
                                         "Authorization": "Bearer " + client.app.state.access_key})
    assert asyncio.run(check()).status_code == 413


def test_validation_does_not_echo_private_input(client):
    secret = "PRIVATE_CONTENT_" * 100
    r = client.post("/api/v1/projects", json={"name": secret})
    assert r.status_code == 422
    assert "PRIVATE_CONTENT" not in r.text


@pytest.mark.parametrize("name", ["/abs.json", "C:/escape.json", "a\\escape.json"])
def test_zip_unsafe_names(client, name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, "{}")
    r = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "a"},
                    files={"file": ("unsafe.zip", buf.getvalue())})
    assert r.status_code == 422
    assert client.get("/api/v1/sources").json()["items"] == []


def test_zip_symlink_rejected(client):
    buf = io.BytesIO()
    info = zipfile.ZipInfo("link.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(info, "target")
    r = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "a"},
                    files={"file": ("symlink.zip", buf.getvalue())})
    assert r.status_code == 422
    assert "symlink" in r.json()["detail"]


@pytest.mark.parametrize("raw", [
    b'{"nexus_fixture":"synthetic-v1","provider":"chatgpt","provider":"claude"}',
    b'{"nexus_fixture":"synthetic-v1","provider":"chatgpt","conversations":[],"x":NaN}',
    b"[" * 2000 + b"0" + b"]" * 2000,
    json.dumps({"nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": [
        {"id": "a", "title": "b", "messages": [{"id": "m", "role": "user", "text": "\ud800"}]}
    ]}).encode(),
])
def test_ambiguous_or_hostile_json_rejected(client, raw):
    r = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "a"},
                    files={"file": ("bad.json", raw)})
    assert r.status_code == 422
    assert client.get("/api/v1/sources").json()["items"] == []


def test_no_browser_cache_of_private_responses(client):
    r = client.get("/api/v1/conversations")
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
