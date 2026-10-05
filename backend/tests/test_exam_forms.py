import io
from datetime import UTC, date, datetime, timedelta

from bson import ObjectId
from pypdf import PdfReader

from tests.academics_fixtures import API, MONDAY, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist, save
from tests.test_marks import marks  # noqa: F401
from tests.test_students import sign_in_as_student


def test_exam_forms_and_hall_tickets(monkeypatch, marks, client, db, sign_in):  # noqa: F811
    t, st, exam = marks["teachers"], marks["students"], marks["exam"]
    rao = t["rao"]["client"]
    slot_id = rao.get(f"{API}/timetable/week", params={"mine": True, "day": MONDAY.isoformat()}).json()["days"][0][
        "lectures"
    ][0]["slot_id"]
    for week, absent in enumerate([[st["2026BCA003"]], [st["2026BCA003"]], [st["2026BCA003"]], []]):
        day = MONDAY + timedelta(days=7 * week)
        at(monkeypatch, ist(day, 10, 5))
        save(rao, slot_id, absent, day=day)
    # Exam fee: Neha still owes ₹1,000.
    head = db.fee_heads.insert_one(
        {"code": "EXAM", "name": "Examination fee", "status": "active", "created_at": datetime.now(UTC)}
    ).inserted_id
    year = ObjectId(marks["year"])
    for prn, due in (("2026BCA001", 0), ("2026BCA002", 100_000), ("2026BCA003", 0)):
        db.ledger_entries.insert_one(
            {"student_id": ObjectId(st[prn]), "academic_year_id": year, "type": "demand", "amount": due,
             "lines": [{"head_id": head, "amount": due}], "at": datetime.now(UTC), "created_by": None}
        )  # fmt: skip

    at(monkeypatch, ist(date(2026, 10, 1), 11))
    body = {
        "name": "Oct-Nov 2026 university exams",
        "term": 1,
        "classes": [{"programme_id": marks["bca"], "year_of_study": 1}],
        "form_deadline": "2026-10-10",
        "seat_prefix": "B",
    }
    assert rao.post(f"{API}/exams/sessions", json=body).status_code == 403
    session = exam.post(f"{API}/exams/sessions", json=body).json()
    sid = session["id"]
    assert session["counts"]["students"] == 3 and session["form_open"]
    papers = [{"subject_id": marks["subjects"]["BCA101"], "date": "2026-11-02", "start": "10:00", "end": "13:00"}]
    exam.patch(f"{API}/exams/sessions/{sid}", json={"papers": papers})

    students = {}
    for prn in st:
        c = new_client(client)
        sign_in_as_student(c, db, prn)
        students[prn] = c
    mine = students["2026BCA001"].get(f"{API}/me/exams").json()[0]
    assert mine["form_status"] == "not_submitted" and [x["code"] for x in mine["subjects"]] == [
        "BCA101",
        "BCA102",
        "BCA103",
    ]
    for c in students.values():
        assert c.post(f"{API}/me/exams/{sid}/form").json()["form_status"] == "submitted"

    rows = {r["prn"]: r for r in exam.get(f"{API}/exams/sessions/{sid}/forms").json()}
    assert rows["2026BCA001"]["eligible"]
    assert not rows["2026BCA002"]["fee_ok"] and rows["2026BCA002"]["fee_due"] == 100_000
    assert not rows["2026BCA003"]["attendance_ok"] and rows["2026BCA003"]["low_subjects"] == ["BCA101 25.0%"]
    assert exam.post(f"{API}/exams/sessions/{sid}/verify-eligible").json() == {"verified": 1, "left": 2}
    verify = lambda prn, **b: exam.post(f"{API}/exams/sessions/{sid}/forms/{st[prn]}/verify", json=b)  # noqa: E731
    assert verify("2026BCA002", approve=True).status_code == 422  # not eligible: needs a reason
    assert verify("2026BCA002", approve=True, reason="Fee paid at the counter today").json()["status"] == "verified"
    assert verify("2026BCA003", approve=False, reason="Attendance below 75%").json()["status"] == "rejected"

    assert (
        exam.patch(f"{API}/exams/sessions/{sid}", json={"hall_tickets_released": True}).status_code == 409
    )  # seats first
    assert exam.post(f"{API}/exams/sessions/{sid}/seat-numbers").json() == {"assigned": 2, "total": 2}
    assert exam.post(f"{API}/exams/sessions/{sid}/seat-numbers").json() == {"assigned": 0, "total": 2}
    assert students["2026BCA001"].get(f"{API}/me/exams/{sid}/hall-ticket.pdf").json()["error"]["code"] == "not_released"
    exam.patch(f"{API}/exams/sessions/{sid}", json={"hall_tickets_released": True})
    pdf = students["2026BCA001"].get(f"{API}/me/exams/{sid}/hall-ticket.pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "HALL TICKET" in text and "B0001" in text and "BCA101" in text and "02 Nov 2026" in text
    assert students["2026BCA003"].get(f"{API}/me/exams/{sid}/hall-ticket.pdf").status_code == 409
    assert students["2026BCA003"].get(f"{API}/me/exams").json()[0]["reason"] == "Attendance below 75%"

    csv = exam.get(f"{API}/exams/sessions/{sid}/export").content.decode("utf-8-sig").splitlines()
    assert csv[0].startswith("PRN,Name,Class,Seat no") and any(
        line.startswith("2026BCA001,Rohan Patil,BCA FY A,B0001") for line in csv
    )

    # After the deadline the form is closed; staff without exam rights can't see forms.
    at(monkeypatch, ist(date(2026, 10, 11), 9))
    assert students["2026BCA003"].post(f"{API}/me/exams/{sid}/form").json()["error"]["code"] == "form_closed"
    assert rao.get(f"{API}/exams/sessions").status_code == 403
    office = marks["office"]
    assert office.get(f"{API}/exams/sessions/{sid}/forms").status_code == 200  # office reads (results.read)
    assert office.post(f"{API}/exams/sessions/{sid}/seat-numbers").status_code == 403
