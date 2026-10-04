from tests.conftest import requires_mongo

AUTH = {"Authorization": "Bearer test-admin-token"}


def test_admin_stats_requires_the_token(client):
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/admin/stats", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_admin_stats_disabled_without_server_token(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN")
    assert client.get("/api/admin/stats", headers=AUTH).status_code == 503


@requires_mongo
def test_admin_stats_aggregates_questions(client, db):
    for q, lang in [("What's the hostel fee?", "en"), ("hostel fee", "hi"), ("weather on mars", "en")]:
        client.post("/api/query", json={"question": q, "language": lang})
    stats = client.get("/api/admin/stats?days=7", headers=AUTH).json()
    assert stats["analytics_enabled"] is True
    assert stats["total_queries"] == 3
    assert stats["by_language"] == {"en": 2, "hi": 1}
    assert stats["by_category"] == {"hostel": 2}
    assert [g["question"] for g in stats["knowledge_gaps"]] == ["weather on mars"]
    assert len(stats["recent"]) == 3
