from copy import deepcopy

import pytest
from conftest import upload


@pytest.mark.parametrize("entity", ["conversation", "message"])
def test_duplicate_ids_in_one_archive_rejected(client, seed_chatgpt, entity):
    fixture = deepcopy(seed_chatgpt)
    conv = fixture["conversations"][0]
    if entity == "conversation":
        fixture["conversations"].append(deepcopy(conv))
    else:
        conv["messages"].append(deepcopy(conv["messages"][0]))
    assert upload(client, "chatgpt", fixture).status_code == 422
    assert client.get("/api/v1/sources").json()["items"] == []


def test_changed_timestamp_rolls_back_entire_batch(client, seed_chatgpt):
    first = upload(client, "chatgpt", seed_chatgpt).json()
    fixture = deepcopy(seed_chatgpt)
    messages = fixture["conversations"][0]["messages"]
    messages.insert(0, {"id": "new", "role": "user", "text": "SHOULD ROLLBACK"})
    messages[1]["created_at"] = "2026-10-12T02:00:00+00:00"
    assert upload(client, "chatgpt", fixture).status_code == 409
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM source_events").fetchone()[0] == 1
    assert client.get("/api/v1/imports/" + first["id"]).status_code == 200
    assert client.get("/api/v1/search", params={"q": "ROLLBACK"}).json()["items"] == []


def test_incremental_dates_and_title_reindexed(client, seed_chatgpt):
    assert upload(client, "chatgpt", seed_chatgpt).status_code == 201
    fixture = deepcopy(seed_chatgpt)
    conv = fixture["conversations"][0]
    conv["title"] = "Renamed 日本語"
    conv["messages"].append({"id": "next", "role": "user", "text": "incremental", 
                              "created_at": "2026-10-12T03:00:00+09:00"})
    counts = upload(client, "chatgpt", fixture).json()["counts"]
    assert counts["messages_inserted"] == 1
    assert counts["messages_duplicates"] == 2
    actual = client.get("/api/v1/conversations").json()["items"][0]
    assert actual["title"] == "Renamed 日本語"
    assert actual["first_at"] == "2026-10-11T02:00:00+00:00"
    assert actual["last_at"] == "2026-10-12T03:00:00+09:00"
    assert len(client.get("/api/v1/search", params={"q": "Renamed"}).json()["items"]) == 3
    assert client.get("/api/v1/search", params={"q": "Roadmap"}).json()["items"] == []


@pytest.mark.parametrize("timestamp", ["yesterday", "2026-99-99T00:00:00Z", "2026-10-11T00:00:00"])
def test_invalid_or_ambiguous_source_timestamp_rejected(client, seed_chatgpt, timestamp):
    fixture = deepcopy(seed_chatgpt)
    fixture["conversations"][0]["messages"][0]["created_at"] = timestamp
    assert upload(client, "chatgpt", fixture).status_code == 422


def test_same_source_ids_are_isolated_by_provider_and_account(client, seed_chatgpt):
    upload(client, "chatgpt", seed_chatgpt, account="one")
    upload(client, "chatgpt", seed_chatgpt, account="two")
    claude = {"nexus_fixture": "synthetic-v1", "provider": "claude", "chats": [
        {"uuid": "chat-1", "name": "Claude", "messages": [
            {"uuid": "msg-1", "sender": "human", "content": "Plan the ark project"}
        ]}
    ]}
    upload(client, "claude", claude, account="one")
    hits = client.get("/api/v1/search", params={"q": "ark"}).json()["items"]
    assert {(h["provider"], h["account_alias"]) for h in hits} == {
        ("chatgpt", "one"), ("chatgpt", "two"), ("claude", "one")
    }
    assert len({h["source_id"] for h in hits}) == 3
