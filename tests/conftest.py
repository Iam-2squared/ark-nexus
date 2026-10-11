import json

import pytest
from fastapi.testclient import TestClient

from nexus.api import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "nexus.sqlite3")) as c:
        yield c


@pytest.fixture
def seed_chatgpt():
    return {
        "nexus_fixture": "synthetic-v1",
        "provider": "chatgpt",
        "conversations": [{
            "id": "chat-1", "title": "Roadmap design",
            "messages": [
                {"id": "msg-1", "role": "user", "text": "Plan the ark project",
                 "created_at": "2026-10-11T02:00:00+00:00"},
                {"id": "msg-2", "role": "assistant", "text": "Milestone verified by tests",
                 "created_at": "2026-10-11T02:01:00+00:00"},
            ],
        }],
    }


def upload(client, provider, data, filename="fixture.json", account="personal", dry_run=False):
    return client.post(
        "/api/v1/imports",
        data={"provider": provider, "account_alias": account, "dry_run": str(dry_run).lower()},
        files={"file": (filename, json.dumps(data).encode("utf-8"), "application/json")},
    )
