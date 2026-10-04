from tests.conftest import requires_mongo


def test_admin_stats_requires_sign_in(client, db):
    r = client.get("/api/v1/admin/stats")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_signed_in"


def test_admin_stats_requires_the_analytics_permission(client, sign_in):
    sign_in(client, ["faculty"])
    assert client.get("/api/v1/admin/stats").status_code == 403


@requires_mongo
def test_admin_stats_aggregates_questions(client, sign_in):
    for q, lang in [("What's the hostel fee?", "en"), ("hostel fee", "hi"), ("weather on mars", "en")]:
        client.post("/api/query", json={"question": q, "language": lang})
    sign_in(client, ["office"])
    stats = client.get("/api/v1/admin/stats?days=7").json()
    assert stats["analytics_enabled"] is True
    assert stats["total_queries"] == 3
    assert stats["by_language"] == {"en": 2, "hi": 1}
    assert stats["by_category"] == {"hostel": 2}
    assert [g["question"] for g in stats["knowledge_gaps"]] == ["weather on mars"]
    assert len(stats["recent"]) == 3
