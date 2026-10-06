from datetime import UTC, date, datetime

from bson import ObjectId

from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"
DAY = date(2026, 10, 5)


def _setup(client, sign_in, db, fees):  # noqa: F811
    """Rohan misses every lecture of the last 4 weeks; Om's first installment is two months late."""
    year = ObjectId(fees["year"])
    div = ObjectId(fees["div"][1])
    ids = {prn: ObjectId(sid) for prn, sid in fees["students"].items()}
    db.students.update_many({}, {"$set": {"division_id": div}})
    subject = db.subjects.insert_one({"code": "BCA101", "name": "Programming in C", "status": "active"}).inserted_id
    days = (
        [f"2026-08-{d:02d}" for d in range(1, 11)]
        + [f"2026-09-{d:02d}" for d in (28, 29, 30)]
        + ["2026-10-01", "2026-10-02", "2026-10-03"]
    )
    for d in days:
        db.attendance_sessions.insert_one(
            {"academic_year_id": year, "division_id": div, "subject_id": subject, "date": d, "start": "09:00",
             "roster": list(ids.values()), "absent": [ids["2026BCA001"]] if d >= "2026-09-28" else []}
        )  # fmt: skip
    db.ledger_entries.insert_one(
        {"student_id": ids["2026BCA003"], "academic_year_id": year, "type": "demand", "amount": 1_000_000,
         "lines": [{"head_id": ObjectId(fees["heads"]["TUITION"]), "amount": 1_000_000}],
         "installments": [{"label": "First installment", "due_date": "2026-08-01", "amount": 1_000_000}],
         "at": datetime(2026, 7, 1, tzinfo=UTC), "created_by": None}
    )  # fmt: skip
    return ids


def test_early_warning_reasons_scopes_notes_and_dashboards(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 10))
    ids = _setup(client, sign_in, db, fees)
    cs = db.departments.find_one({"code": "CS"})["_id"]
    other = db.departments.insert_one({"code": "COM", "name": "Commerce", "status": "active"}).inserted_id
    office, principal, hod, hod2, mentor, teacher, accounts = (new_client(client) for _ in range(7))
    sign_in(office, ["office"])
    sign_in(principal, ["principal"])
    h = sign_in(hod, ["hod"])
    h2 = sign_in(hod2, ["hod"])
    m = sign_in(mentor, ["mentor"], name="Amit Deshmukh")
    sign_in(teacher, ["faculty"])
    sign_in(accounts, ["accounts"])
    db.users.update_one({"_id": h["_id"]}, {"$set": {"department_id": cs}})
    db.users.update_one({"_id": h2["_id"]}, {"$set": {"department_id": other}})

    # The office makes Amit the mentor of the class.
    view = office.get(f"{API}/mentoring/assignments", params={"division_id": fees["div"][1]}).json()
    assert [s["prn"] for s in view["students"]] == ["2026BCA001", "2026BCA002", "2026BCA003"]
    assert "Amit Deshmukh" in [x["name"] for x in view["mentors"]]
    body = {"mentor_id": str(m["_id"]), "student_ids": [str(i) for i in ids.values()]}
    assert office.put(f"{API}/mentoring/assignments", json=body).json() == {"updated": 3}
    assert hod2.put(f"{API}/mentoring/assignments", json=body).status_code == 403  # not their department

    # The Principal runs the rules now (the daily job does it every morning).
    assert principal.post(f"{API}/risk/recompute").json() == {"students": 3, "high": 1, "medium": 1}
    mine = mentor.get(f"{API}/mentoring/mentees").json()
    rohan, om, neha = mine["students"]
    assert (rohan["prn"], rohan["level"]) == ("2026BCA001", "high")
    assert rohan["reasons"] == [
        "Attendance 62.5% (minimum 75%)",
        "Attendance fell from 100% to 0% in the last 4 weeks",
    ]
    assert (om["level"], om["reasons"]) == ("medium", ["Fees of Rs. 10,000.00 overdue for 65 days"])
    assert neha["level"] == "none" and mine["high"] == 1

    # Counselling notes: the mentor writes one; the HOD sees it, the other HOD sees nothing.
    note = {
        "text": "Talked to Rohan: he works mornings at his uncle's shop. Will move to the afternoon batch.",
        "follow_up_on": "2026-10-12",
    }
    out = mentor.post(f"{API}/risk/students/{ids['2026BCA001']}/notes", json=note).json()
    assert out["history"][0]["by"] == "Amit Deshmukh" and out["notes"] == 1
    assert [s["prn"] for s in hod.get(f"{API}/risk").json()["students"]] == ["2026BCA001", "2026BCA003"]
    assert hod.get(f"{API}/risk/students/{ids['2026BCA001']}").json()["follow_up_on"] == "2026-10-12"
    assert hod2.get(f"{API}/risk").json()["students"] == []
    assert hod2.get(f"{API}/risk/students/{ids['2026BCA001']}").status_code == 404
    entry = db.audit_log.find_one({"action": "mentoring.note_added"})
    assert "details" not in entry or "uncle" not in str(entry["details"])  # the note itself isn't logged

    # Never the student, the office or a teacher who isn't the mentor.
    rohan_c = new_client(client)
    sign_in_as_student(rohan_c, db, "2026BCA001")
    for c in (rohan_c, office, teacher):
        assert c.get(f"{API}/risk").status_code == 403
        assert c.get(f"{API}/risk/students/{ids['2026BCA001']}").status_code in (403, 404)
    export = rohan_c.get(f"{API}/me/data-export").text
    assert "uncle" not in export and "fell from" not in export
    assert "risk" not in rohan_c.get(f"{API}/dashboard").json()

    # Rules are settings: without the "falling attendance" rule Rohan is only "medium".
    rules = principal.get(f"{API}/risk/rules").json()
    rules["attendance_drop"]["on"] = False
    principal.put(f"{API}/risk/rules", json=rules)
    principal.post(f"{API}/risk/recompute")
    assert db.risk_flags.find_one({"_id": ids["2026BCA001"]})["level"] == "medium"

    # Dashboards: the Principal's overview, Accounts' receivables, the HOD's and mentor's counts.
    dash = principal.get(f"{API}/dashboard").json()
    assert dash["overview"]["risk"] == {"high": 0, "medium": 2}
    assert dash["overview"]["attendance"]["below_minimum"] == 1
    assert dash["overview"]["fees"]["outstanding"] == 1_000_000
    money = accounts.get(f"{API}/dashboard").json()["accounts"]
    assert money["receivables"] == {
        "total": 1_000_000,
        "overdue": 1_000_000,
        "overdue_students": 1,
        "by_year": [{"year_of_study": 1, "amount": 1_000_000}],
    }
    assert hod.get(f"{API}/dashboard").json()["risk"] == {"high": 0, "medium": 2}
    assert mentor.get(f"{API}/dashboard").json()["risk"] == {"high": 0, "medium": 2}
    assert "risk" not in teacher.get(f"{API}/dashboard").json()
