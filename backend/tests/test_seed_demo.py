import dataclasses

from app.core.config import settings
from scripts import seed_demo


def test_refuses_production_database_without_force(db, monkeypatch, capsys):
    monkeypatch.setattr(seed_demo, "settings", dataclasses.replace(settings, mongodb_db="collegeconnect"))
    assert seed_demo.main([]) == 2
    assert "Refusing" in capsys.readouterr().err


def test_seeds_and_resets_only_demo_data(db):
    db.queries.insert_one({"question": "a real student question"})
    assert seed_demo.main([]) == 0
    assert db.queries.count_documents({"demo": True}) == 60
    assert seed_demo.main(["--reset"]) == 0
    assert db.queries.count_documents({"demo": True}) == 60  # reset then re-seeded
    assert db.queries.count_documents({"question": "a real student question"}) == 1
