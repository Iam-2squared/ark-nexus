from copy import deepcopy

from conftest import upload


def test_long_history_pagination_and_accurate_overview(client, seed_chatgpt):
    fixture = deepcopy(seed_chatgpt)
    fixture["conversations"] = [
        {"id": f"c{i}", "title": f"Thread {i}", "messages": [
            {"id": "m", "role": "user", "text": "日本語 common history"}
        ]} for i in range(505)
    ]
    upload(client, "chatgpt", fixture)
    long = {"nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": [
        {"id": "long", "title": "Long", "messages": [
            {"id": f"m{i}", "role": "user", "text": f"日本語 entry {i}"} for i in range(1101)
        ]}
    ]}
    upload(client, "chatgpt", long)
    page = client.get("/api/v1/conversations", params={"offset": 500, "limit": 100}).json()
    assert page["total"] == 506
    assert len(page["items"]) == 6
    assert page["next_offset"] is None
    first = client.get("/api/v1/conversations", params={"limit": 1}).json()
    assert first["next_offset"] == 1
    cid = first["items"][0]["id"]
    msgs = client.get(f"/api/v1/conversations/{cid}/messages",
                      params={"offset": 1000, "limit": 100}).json()
    assert msgs["total"] == 1101
    assert len(msgs["items"]) == 100
    assert msgs["items"][0]["external_id"] == "m1000"
    assert msgs["next_offset"] == 1100
    search = client.get("/api/v1/search", params={"q": "日本語", "offset": 1500}).json()
    assert search["total"] == 1606
    assert len(search["items"]) == 100
    assert search["next_offset"] == 1600
    overview = client.get("/api/v1/overview").json()
    assert overview["counts"] == {"sources": 1, "conversations": 506, "messages": 1606,
                                   "projects": 0, "imports": 2}


def test_import_history_has_provenance_and_receipts(client, seed_chatgpt):
    first = upload(client, "chatgpt", seed_chatgpt).json()
    second = upload(client, "chatgpt", seed_chatgpt).json()
    page = client.get("/api/v1/imports", params={"limit": 1}).json()
    assert page["total"] == 2
    assert page["next_offset"] == 1
    recent = page["items"][0]
    assert recent["id"] == second["id"]
    assert recent["provider"] == "chatgpt"
    assert recent["account_alias"] == "personal"
    assert recent["status"] == "imported"
    assert recent["counts"]["messages_inserted"] == 0
    assert recent["counts"]["messages_duplicates"] == 2
    assert recent["data_kind"] == "synthetic"
    assert client.get("/api/v1/imports/" + first["id"]).json()["counts"]["messages_inserted"] == 2


def test_invalid_pagination_and_missing_conversation(client):
    for endpoint in ("conversations", "imports", "search?q=x"):
        separator = "&" if "?" in endpoint else "?"
        assert client.get(f"/api/v1/{endpoint}{separator}offset=-1").status_code == 422
        assert client.get(f"/api/v1/{endpoint}{separator}limit=0").status_code == 422
    assert client.get("/api/v1/conversations/missing/messages").status_code == 404


def test_project_counts_are_not_limited_to_current_page(client, seed_chatgpt):
    upload(client, "chatgpt", seed_chatgpt)
    cid = client.get("/api/v1/conversations").json()["items"][0]["id"]
    p = client.post("/api/v1/projects", json={"name": "Example"}).json()
    client.patch("/api/v1/conversations/" + cid, json={"project_id": p["id"]})
    assert client.get("/api/v1/projects").json()["items"][0]["conversation_count"] == 1
