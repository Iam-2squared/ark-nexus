import io
import json
import zipfile

from conftest import upload


def test_health_and_no_claimed_sync(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["external_providers_connected"] is False
    assert "real export parsing not validated" in client.get("/api/v1/sources").json()["limitations"]


def test_chatgpt_idempotence_and_receipt(client, seed_chatgpt):
    first = upload(client, "chatgpt", seed_chatgpt)
    assert first.status_code == 201, first.text
    assert first.json()["counts"]["messages_inserted"] == 2
    second = upload(client, "chatgpt", seed_chatgpt)
    assert second.json()["counts"]["messages_inserted"] == 0
    assert second.json()["counts"]["messages_duplicates"] == 2
    receipt = client.get("/api/v1/imports/" + first.json()["id"]).json()
    assert receipt["parser_version"] == "synthetic-fixture-1"
    assert receipt["counts"]["conversations_inserted"] == 1
    assert len(client.get("/api/v1/conversations").json()["items"]) == 1
    assert len(client.get("/api/v1/search", params={"q": "ark"}).json()["items"]) == 1


def test_claude_and_project_mapping(client):
    data = {"nexus_fixture": "synthetic-v1", "provider": "claude", "chats": [
        {"uuid": "c-1", "name": "日本語のメモ", "messages": [
            {"uuid": "cm-1", "sender": "human", "content": "日本語の共同作業", "created_at": None},
        ]},
    ]}
    result = upload(client, "claude", data)
    assert result.status_code == 201, result.text
    convo = client.get("/api/v1/conversations").json()["items"][0]
    project = client.post("/api/v1/projects", json={"name": "ARK Nexus"}).json()
    assert client.patch("/api/v1/conversations/" + convo["id"],
                        json={"project_id": project["id"]}).status_code == 200
    found = client.get("/api/v1/search", params={"q": "日本語", "project_id": project["id"]}).json()
    assert len(found["items"]) == 1
    assert found["items"][0]["provider"] == "claude"
    assert found["items"][0]["project_id"] == project["id"]
    assert len(client.get("/api/v1/search", params={"q": "日本語", "source_id": "fake"}).json()["items"]) == 0


def test_reject_unverified_real_export(client):
    response = upload(client, "chatgpt", {"conversations": [{"mapping": {}}]})
    assert response.status_code == 422
    assert "Unsupported real export format" in response.json()["detail"]


def test_dry_run_no_writes(client, seed_chatgpt):
    result = upload(client, "chatgpt", seed_chatgpt, dry_run=True)
    assert result.status_code == 201
    assert result.json()["persisted"] is False
    assert client.get("/api/v1/conversations").json()["items"] == []


def test_malicious_zip_rejected(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../fixture.json", '{"nexus_fixture": "synthetic-v1"}')
    r = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "a"},
                    files={"file": ("bad.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 422
    assert "unsafe archive path" in r.json()["detail"]
    assert client.get("/api/v1/conversations").json()["items"] == []


def test_zip_with_fixture_accepted(client, seed_chatgpt):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("fixtures/chat.json", json.dumps(seed_chatgpt))
    r = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "a"},
                    files={"file": ("fixture.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 201, r.text


def test_origin_cross_site_write_blocked(client, seed_chatgpt):
    result = client.post("/api/v1/projects", headers={"Origin": "https://example.com"},
                         json={"name": "Wrong"})
    assert result.status_code == 403
    assert client.get("/api/v1/projects").json()["items"] == []


def test_1000_message_reimport(client):
    fixture = {"nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": [
        {"id": "chat-load", "title": "Batch Fixture", "messages": [
            {"id": f"m{i}", "role": "user", "text": f"searchable token{i:04d}"}
            for i in range(1000)
        ]}
    ]}
    assert upload(client, "chatgpt", fixture).json()["counts"]["messages_inserted"] == 1000
    second = upload(client, "chatgpt", fixture)
    assert second.json()["counts"]["messages_inserted"] == 0
    assert second.json()["counts"]["messages_duplicates"] == 1000
    for i in range(30):
        hits = client.get("/api/v1/search", params={"q": f"token{i:04d}"}).json()["items"]
        assert len(hits) == 1, i
        assert hits[0]["content"] == f"searchable token{i:04d}"


def test_conflicting_message_identity_rolls_back(client, seed_chatgpt):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    mutated = json.loads(json.dumps(seed_chatgpt))
    mutated["conversations"][0]["messages"][0]["text"] = "MUTATED CONTENT"
    failed = upload(client, "chatgpt", mutated)
    assert failed.status_code == 409
    assert "revision-aware" in failed.json()["detail"]
    assert len(client.get("/api/v1/search", params={"q": "MUTATED"}).json()["items"]) == 0
    assert len(client.get("/api/v1/conversations").json()["items"]) == 1
