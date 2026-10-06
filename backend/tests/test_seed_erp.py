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
    # Exams: schemes for every subject, marks in two states, forms, last year's results.
    assert db.assessment_schemes.count_documents({}) == 15
    assert {s["status"] for s in db.marks_sheets.find({})} == {"approved", "published"}
    assert db.exam_forms.count_documents({"status": "submitted"}) == counts["exam forms"] == 10
    assert db.results.count_documents({}) == 20 and counts["results"] == 100
    # Certificates: one issued, one verified, two waiting (one of them late).
    assert counts["certificate requests"] == 4
    by_status = sorted(r["status"] for r in db.certificate_requests.find({}))
    assert by_status == ["ready", "requested", "requested", "verified"]
    # Parents: one account with two children.
    assert [len(p["children"]) for p in db.users.find({"kind": "parent"})] == [2]
    # Admissions: one open cycle, applicants at each stage, enquiries.
    by_status = sorted(a["status"] for a in db.applications.find({}))
    assert counts["applications"] == 5 and by_status == ["draft", "submitted", "verified", "verified", "verified"]
    assert db.enquiries.count_documents({}) == 2 and db.admission_cycles.find_one({})["status"] == "open"
    # Campus: library loans (one overdue), hostel residents with requests, placement drives.
    assert db.books.count_documents({}) == 6 and db.loans.count_documents({"status": "open"}) == 4
    assert db.hostel_allotments.count_documents({"status": "active"}) == 4 and db.outpasses.count_documents({}) == 1
    assert db.drives.count_documents({}) == 2 and counts["placement registrations"] >= 5
    assert db.drive_registrations.count_documents({"status": "selected"}) == 1
    # People: staff records, leave waiting for the HOD and one teacher away, grievances.
    assert db.staff_profiles.count_documents({"teaching": True}) == counts["staff records"] == 11
    assert sorted(r["status"] for r in db.leave_requests.find({})) == ["approved", "pending"]
    assert sorted(g["status"] for g in db.grievances.find({})) == ["open", "open", "resolved"]
    assert db.grievances.count_documents({"anonymous": True}) == 1


def test_seed_refuses_production(monkeypatch, capsys):
    monkeypatch.setattr(seed_demo, "settings", replace(settings, mongodb_db=seed_demo.PRODUCTION_DB))
    assert seed_demo.main(["--erp"]) == 2
    assert "Refusing" in capsys.readouterr().err
