"""Thirty fixed mixed-language/literal/filter cases, additive to the original token cases."""

import pytest
from conftest import upload

CASES = [
    ("Alpha", None, None, {"en", "cl"}),
    ("ARK", None, None, {"en", "cl", "other"}),
    ("roadmap", None, None, {"en"}),
    ("Design notes", None, None, {"en"}),
    ("100%", None, None, {"en"}),
    ("5%", None, None, {"tiny"}),
    ("%", None, None, {"en", "tiny"}),
    ("_", None, None, {"en", "tiny"}),
    ("build_step", None, None, {"en"}),
    ("C:\\nexus", None, None, {"en"}),
    ("'single'", None, None, {"quote"}),
    ('"double"', None, None, {"quote"}),
    ("OR 1=1 --", None, None, {"quote"}),
    ("x' OR 1=1 --", None, None, set()),
    ("日本語", None, None, {"ja", "cl"}),
    ("会話", None, None, {"ja"}),
    ("短い", None, None, {"tiny"}),
    ("メモ", None, None, {"tiny"}),
    ("🚀", None, None, {"ja"}),
    ("検証完了", None, None, {"ja"}),
    ("missing", None, None, set()),
    ("", None, None, set()),
    ("   ", None, None, set()),
    ("ark", "cg", None, {"en"}),
    ("ark", "claude", None, {"cl"}),
    ("ark", None, "p1", {"en"}),
    ("日本語", None, "p1", {"ja"}),
    ("ark", "cg", "p2", set()),
    ("ark", "other", None, {"other"}),
    ("ark", "missing", None, set()),
]


@pytest.fixture
def search_catalog(client):
    records = [
        ("chatgpt", "one", "en", "Design notes", "Alpha ARK roadmap 100% build_step C:\\nexus", "p1"),
        ("chatgpt", "one", "ja", "日本語設計", "会話履歴を安全に統合。検証完了 🚀", "p1"),
        ("chatgpt", "one", "quote", "Error handling", "quotes 'single' \"double\" OR 1=1 --", None),
        ("claude", "one", "cl", "Claude review", "alpha ark 日本語 review", "p2"),
        ("claude", "one", "tiny", "Tiny", "短いメモ 率5% x_y", None),
        ("chatgpt", "two", "other", "Other account", "ark separate account", None),
    ]
    projects = {key: client.post("/api/v1/projects", json={"name": key}).json()["id"]
                for key in ("p1", "p2")}
    sources = {}
    for provider, account, mid, title, text, project in records:
        if provider == "chatgpt":
            data = {"nexus_fixture": "synthetic-v1", "provider": provider, "conversations": [
                {"id": mid, "title": title, "messages": [{"id": mid, "role": "user", "text": text}]}
            ]}
        else:
            data = {"nexus_fixture": "synthetic-v1", "provider": provider, "chats": [
                {"uuid": mid, "name": title, "messages": [{"uuid": mid, "sender": "human", "content": text}]}
            ]}
        result = upload(client, provider, data, account=account)
        assert result.status_code == 201
        key = "claude" if provider == "claude" else "cg" if account == "one" else "other"
        sources[key] = result.json()["source_id"]
        if project:
            conv = client.get("/api/v1/conversations",
                              params={"source_id": result.json()["source_id"]}).json()["items"][0]
            assert client.patch("/api/v1/conversations/" + conv["id"],
                                json={"project_id": projects[project]}).status_code == 200
    return sources, projects


@pytest.mark.parametrize("query,source,project,expected", CASES,
                         ids=[f"search-{i:02}" for i in range(1, 31)])
def test_fixed_search_case(client, search_catalog, query, source, project, expected):
    sources, projects = search_catalog
    params = {"q": query}
    if source:
        params["source_id"] = sources.get(source, "not-a-source")
    if project:
        params["project_id"] = projects[project]
    response = client.get("/api/v1/search", params=params)
    assert response.status_code == 200
    page = response.json()
    assert {r["external_message_id"] for r in page["items"]} == expected
    assert page["total"] == len(expected)
