def test_health_reports_pipeline_modes(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["rag_pipeline"]["retrieval"] == "bm25"
    assert body["rag_pipeline"]["generation"] == "extractive"
    assert body["rag_pipeline"]["documents"] >= 6


def test_categories_cover_all_offices_in_three_languages(client):
    cats = client.get("/api/categories").json()
    assert {c["id"] for c in cats} == {"admissions", "fees", "examinations", "placements", "hostel", "notices"}
    for c in cats:
        assert c["label_en"] and c["label_hi"] and c["label_mr"]
