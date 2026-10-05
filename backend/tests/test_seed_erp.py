import random
from dataclasses import replace

from app.core.config import settings
from scripts import seed_demo, seed_erp


def test_erp_seed_builds_a_consistent_demo(db):
    counts = seed_erp.seed(db, random.Random(1))  # noqa: S311 - demo data
    assert counts["students"] == 60 and db.students.count_documents({}) == 60
    assert {s["year_of_study"] for s in db.students.find({}, {"year_of_study": 1})} == {1, 2, 3}
    assert db.receipts.count_documents({}) == counts["receipts"] > 0
    # Every receipt has its payment in the ledger, and numbers have no gaps.
    assert db.ledger_entries.count_documents({"type": "payment"}) == counts["receipts"]
    assert db.ledger_entries.count_documents({"type": "demand"}) == 60
    assert db.approvals.count_documents({"status": "pending"}) == 1
    assert db.notices.count_documents({}) == 3
    assert db.sessions.count_documents({}) == 0  # the seeder's own sessions are removed
    assert db.users.count_documents({"kind": "student", "must_change_password": False}) == 60
    # Academics: subjects, a timetable per class, past attendance, teachers in the department.
    assert db.timetables.count_documents({}) == 3 and db.subjects.count_documents({}) == 15
    assert db.attendance_sessions.count_documents({}) == counts["lectures marked"]
    assert db.users.count_documents({"roles": "faculty", "department_id": {"$exists": True}}) == 9
    assert db.students.count_documents({"batch": "B1"}) == 30


def test_seed_refuses_production(monkeypatch, capsys):
    monkeypatch.setattr(seed_demo, "settings", replace(settings, mongodb_db=seed_demo.PRODUCTION_DB))
    assert seed_demo.main(["--erp"]) == 2
    assert "Refusing" in capsys.readouterr().err
