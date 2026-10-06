import pytest
from pymongo import IndexModel

from app.core import db as core_db
from app.core.errors import AppError


def test_v1_and_legacy_paths_both_work(client):
    for prefix in ("/api/v1", "/api"):
        assert client.get(f"{prefix}/health").status_code == 200
        r = client.post(f"{prefix}/query", json={"question": "What's the hostel fee?"})
        assert r.status_code == 200 and r.json()["grounded"] is True


def test_docs_only_list_v1_paths(client):
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert "/api/v1/query" in paths
    assert not any(p.startswith("/api/query") for p in paths)


def test_errors_use_one_format(client, db):
    assert client.get("/api/v1/auth/me").json() == {"error": {"code": "not_signed_in", "message": "Please sign in."}}
    assert client.get("/api/v1/does-not-exist").json()["error"]["code"] == "not_found"

    body = client.post("/api/v1/query", json={"question": "", "language": "en"}).json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "question"


def test_unexpected_errors_hide_details(client, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.modules.helpdesk import router as helpdesk

    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(helpdesk, "answer_question", boom)
    r = TestClient(app, raise_server_exceptions=False).post("/api/v1/query", json={"question": "fees"})
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}}


def test_app_error_carries_code_and_field():
    err = AppError(409, "PRN already exists", field="prn")
    assert (err.status, err.code, err.field) == (409, "conflict", "prn")


def test_transaction_commits(db):
    def work(session):
        db.counters.insert_one({"_id": "receipt:2026-27", "seq": 1}, session=session)
        db.ledger.insert_one({"amount_paise": 100}, session=session)
        return "done"

    assert core_db.run_in_transaction(work) == "done"
    assert db.counters.count_documents({}) == 1 and db.ledger.count_documents({}) == 1


def test_transaction_rolls_back_everything_on_error(db):
    for name in ("counters", "ledger"):  # transactions need the collections to exist already
        if name not in db.list_collection_names():
            db.create_collection(name)

    def work(session):
        db.counters.insert_one({"_id": "receipt:2026-27", "seq": 1}, session=session)
        raise ValueError("payment failed half way")

    with pytest.raises(ValueError):
        core_db.run_in_transaction(work)
    assert db.counters.count_documents({}) == 0


def test_registered_indexes_are_created(db, monkeypatch):
    monkeypatch.setattr(core_db, "_index_registry", {"widgets": [IndexModel([("code", 1)], unique=True)]})
    core_db.ensure_indexes(db)
    assert any(ix.get("unique") for ix in db.widgets.list_indexes())
