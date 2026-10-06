from datetime import UTC, date, datetime

from bson import ObjectId

from tests.academics_fixtures import API, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist
from tests.test_marks import marks, scheme  # noqa: F401
from tests.test_students import sign_in_as_student


def test_staff_dashboards_follow_roles(monkeypatch, marks, client, db, sign_in):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 9, 30))  # Monday, during Rao's BCA101 lecture
    t, s = marks["teachers"], marks["subjects"]
    scheme(t["hod"]["client"], s["BCA101"])

    rao = t["rao"]["client"].get(f"{API}/dashboard").json()
    assert set(rao) == {"teaching"}
    lecture = rao["teaching"]["lectures"][0]
    assert lecture["code"] == "BCA101" and lecture["takeable"] and not lecture["taken"]
    assert [x["label"].split(" · ")[1] for x in rao["teaching"]["marks_tasks"]] == ["BCA101"]

    hod = t["hod"]["client"].get(f"{API}/dashboard").json()["hod"]
    assert [c["students"] for c in hod["classes"]] == [3, 0, 0]
    assert hod["attendance_requests"] == 0 and hod["workload"] == [{"name": "Anita Rao", "hours": 1.0}]
    comhod = t["comhod"]["client"].get(f"{API}/dashboard").json()["hod"]
    assert [c["students"] for c in comhod["classes"]] == [0] and comhod["workload"] == []  # own department only

    exam = marks["exam"].get(f"{API}/dashboard").json()
    assert set(exam) == {"exam_cell"} and exam["exam_cell"]["sessions"] == []

    sid = ObjectId(marks["students"]["2026BCA001"])
    db.certificate_requests.insert_many(
        [
            {"student_id": sid, "type": "bonafide", "status": "requested", "due_date": "2026-10-01"},
            {"student_id": sid, "type": "tc", "status": "verified", "due_date": "2026-10-20"},
        ]
    )
    office = marks["office"].get(f"{API}/dashboard").json()["office"]
    assert office["certificates_open"] == 2 and office["certificates_overdue"] == 1
    principal = new_client(client)
    sign_in(principal, ["principal"])
    p = principal.get(f"{API}/dashboard").json()["principal"]
    assert p["certificates_to_sign"] == 1 and p["certificates_overdue"] == 1

    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert student.get(f"{API}/dashboard").json() == {}


def test_student_home_cards_for_exams_and_certificates(monkeypatch, marks, client, db):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 1), 11))
    db.fee_heads.insert_one({"code": "EXAM", "name": "Examination fee", "status": "active"})
    r = marks["exam"].post(
        f"{API}/exams/sessions",
        json={
            "name": "Oct-Nov 2026 university exams",
            "term": 1,
            "classes": [{"programme_id": marks["bca"], "year_of_study": 1}],
            "form_deadline": "2026-10-10",
            "seat_prefix": "B",
        },
    )
    assert r.status_code == 201, r.text
    db.certificate_requests.insert_one(
        {
            "student_id": ObjectId(marks["students"]["2026BCA001"]),
            "type": "bonafide",
            "status": "ready",
            "issued_at": datetime(2026, 9, 30, 6, tzinfo=UTC),
        }
    )
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    cards = {c["kind"]: c for c in student.get(f"{API}/me/home").json()["cards"]}
    assert cards["exam_form"]["due_date"] == "2026-10-10" and cards["exam_form"]["severity"] == "warning"
    assert cards["certificate_ready"]["type"] == "bonafide"
    assert "hall_ticket" not in cards and "results" not in cards
