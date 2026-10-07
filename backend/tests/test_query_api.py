from tests.conftest import requires_mongo


@requires_mongo
def test_answers_need_a_sign_in(client, db, sign_in):
    r = client.post("/api/query", json={"question": "What's the hostel fee?", "language": "en"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_signed_in"


@requires_mongo
def test_query_returns_cited_answer(client, sign_in):
    sign_in(client, ["faculty"])
    body = client.post("/api/query", json={"question": "What's the hostel fee?", "language": "en"}).json()
    assert body["grounded"] is True
    assert body["category"] == "hostel"
    assert body["sources"][0]["document"] == "Hostel_Facilities_Notice_2026.pdf"


@requires_mongo
def test_query_validates_input(client, sign_in):
    sign_in(client, ["faculty"])
    assert client.post("/api/query", json={"question": "", "language": "en"}).status_code == 422
    assert client.post("/api/query", json={"question": "fees", "language": "fr"}).status_code == 422
    assert client.post("/api/query", json={"question": "x" * 501}).status_code == 422


@requires_mongo
def test_each_question_is_logged_without_blocking_the_answer(client, db, sign_in):
    sign_in(client, ["faculty"])
    client.post("/api/query", json={"question": "What's the hostel fee?", "language": "en"})
    client.post("/api/query", json={"question": "weather on mars", "language": "hi", "category": "hostel"})
    logs = list(db.queries.find({}, {"_id": 0}).sort("created_at", 1))
    assert [q["question"] for q in logs] == ["What's the hostel fee?", "weather on mars"]
    assert logs[0]["grounded"] is True and logs[0]["category"] == "hostel"
    assert "user_id" not in logs[0]  # never who asked
    # Unanswered questions only count towards an office if the student filtered to it.
    assert logs[1]["grounded"] is False and logs[1]["category"] == "hostel"
