from nexus.store import Store


def test_migration_is_repeatable(tmp_path):
    path = tmp_path / "nexus.sqlite3"
    Store(path)
    two = Store(path)
    with two.connect() as db:
        assert [r[0] for r in db.execute("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2]


def test_search_does_not_execute_sql(client, seed_chatgpt):
    from conftest import upload

    upload(client, "chatgpt", seed_chatgpt)
    response = client.get("/api/v1/search", params={"q": "ark' OR 1=1 --"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 2
