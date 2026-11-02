"""A cold start reads one marker instead of re-creating every index (slow over the network)."""

from app.core import db as core_db


def test_indexes_are_created_once_then_skipped_while_unchanged(db, monkeypatch):
    calls = []
    real = core_db.ensure_indexes
    monkeypatch.setattr(core_db, "ensure_indexes", lambda database: (calls.append(1), real(database)))

    db.app_meta.delete_many({})
    monkeypatch.setattr(core_db, "_indexes_ready", False)
    core_db.get_db()
    assert calls == [1]  # no marker yet: indexes created, marker written
    assert db.app_meta.find_one({"_id": "indexes"})["fingerprint"] == core_db.index_fingerprint()

    monkeypatch.setattr(core_db, "_indexes_ready", False)  # a new serverless instance
    core_db.get_db()
    assert calls == [1]  # unchanged: skipped

    db.app_meta.update_one({"_id": "indexes"}, {"$set": {"fingerprint": "old"}})
    monkeypatch.setattr(core_db, "_indexes_ready", False)  # a deploy that changed an index
    core_db.get_db()
    assert calls == [1, 1]


def test_health_reports_the_database_round_trip(client, db):
    body = client.get("/api/v1/health").json()
    assert isinstance(body["db_ms"], float) and body["db_ms"] >= 0
