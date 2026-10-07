"""Deadline radar (plan 5.6) and the knowledge-gap loop (plan 5.7)."""

from datetime import date, timedelta

import pytest
from bson import ObjectId

from app.core import clock
from app.modules.deadlines import service as deadlines
from app.rag import generator, store
from app.rag.generator import ExtractedDeadline
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean_kb(db):
    yield
    for name in ("kb_meta", "kb_documents", "kb_chunks"):
        db[name].delete_many({})
    store._cached.update(version=None, index=None)


def test_dates_found_in_text():
    today = date(2026, 10, 6)
    found = deadlines.find_dates(
        "Exam forms",
        "Exam forms close on 15th October 2026. Late forms till 20/10/2026 with a fine. "
        "Fees are due 2026-11-05.\nThe practical exam starts on Nov 12. Admissions closed on 1 July 2026.",
        today,
    )
    assert [f["date"] for f in found] == ["2026-10-15", "2026-10-20", "2026-11-05", "2026-11-12"]
    assert found[0]["what"]["en"] == "Exam forms close on 15th October 2026"
    assert deadlines.find_dates("", "Results on 5 January.", today)[0]["date"] == "2027-01-05"  # next one
    assert deadlines.find_dates("", "Room 15 Oct block; call 31/02/2026", today) == [
        {"date": "2026-10-15", "what": {"en": "Room 15 Oct block; call 31/02/2026"}}
    ]  # an impossible date is skipped


def test_deadline_radar_from_notice_to_reminder(client, sign_in, fees, db):  # noqa: F811
    from app.modules.jobs import router as jobs  # noqa: F401 - the daily job runs deadlines.daily

    office = new_client(client)
    sign_in(office, ["office"])
    rohan, om = new_client(client), new_client(client)
    sign_in_as_student(rohan, db, "2026BCA001")
    sign_in_as_student(om, db, "2026BCA003")
    db.students.update_one({"prn": "2026BCA003"}, {"$set": {"year_of_study": 2}})
    today = clock.today()
    soon = today + timedelta(days=3)
    body = f"Submit the exam form at the office by {soon:%d %B %Y}. Bring two photos."
    n = office.post(
        f"{API}/notices",
        json={
            "title": "FY BCA exam form",
            "body": body,
            "audience": {"kind": "class", "programme_id": fees["bca"], "year_of_study": 1},
        },
    ).json()
    found = office.get(f"{API}/notices/{n['id']}/deadlines").json()
    assert [(d["date"], d["status"], d["source"]) for d in found] == [(soon.isoformat(), "proposed", "pattern")]
    assert rohan.get(f"{API}/me/deadlines").json() == []  # nothing reaches students unchecked
    assert rohan.get(f"{API}/notices/{n['id']}/deadlines").status_code == 403

    later = today + timedelta(days=4)
    d = office.patch(
        f"{API}/deadlines/{found[0]['id']}",
        json={
            "status": "confirmed",
            "date": later.isoformat(),
            "what": "Submit the exam form",
            "what_mr": "परीक्षा अर्ज जमा करा",
        },
    ).json()
    assert d["status"] == "confirmed" and d["what"] == {"en": "Submit the exam form", "mr": "परीक्षा अर्ज जमा करा"}
    mine = rohan.get(f"{API}/me/deadlines").json()
    assert [(x["date"], x["days_left"]) for x in mine] == [(later.isoformat(), 4)]
    card = next(c for c in rohan.get(f"{API}/me/home").json()["cards"] if c["kind"] == "deadline")
    assert card["what_mr"] == "परीक्षा अर्ज जमा करा" and card["severity"] == "info" and card["notice_id"] == n["id"]
    assert om.get(f"{API}/me/deadlines").json() == []  # another class

    # Editing the notice proposes again but keeps what staff decided.
    office.patch(
        f"{API}/notices/{n['id']}", json={"body": body + f" Late forms till {(today + timedelta(days=9)):%d/%m/%Y}."}
    )
    statuses = sorted(x["status"] for x in office.get(f"{API}/notices/{n['id']}/deadlines").json())
    assert statuses == ["confirmed", "proposed"]

    # Reminders: 3 days before and on the day, once per student.
    fy = {ObjectId(fees["students"][p]) for p in ("2026BCA001", "2026BCA002")}  # the class (Om moved to SY)
    assert deadlines.daily(today + timedelta(days=1)) == {"reminders": 2}
    assert deadlines.daily(today + timedelta(days=1)) == {"reminders": 0}
    assert deadlines.daily(later) == {"reminders": 2}
    queued = list(db.message_queue.find({"template": "deadline_soon"}))
    assert len(queued) == 4 and {q["student_id"] for q in queued} == fy

    added = office.post(
        f"{API}/notices/{n['id']}/deadlines", json={"date": (today - timedelta(days=1)).isoformat(), "what": "Old"}
    )
    assert added.status_code == 422
    office.patch(f"{API}/notices/{n['id']}", json={"status": "withdrawn", "reason": "Wrong class"})
    assert rohan.get(f"{API}/me/deadlines").json() == []  # gone with the notice
    assert db.audit_log.count_documents({"action": "deadlines.confirmed"}) == 1


def test_ai_finds_deadlines_in_three_languages(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    office = new_client(client)
    sign_in(office, ["office"])
    when = (clock.today() + timedelta(days=10)).isoformat()
    monkeypatch.setattr(generator, "llm_available", lambda: True)
    monkeypatch.setattr(generator, "translate_notice", lambda t, b: None)
    monkeypatch.setattr(
        generator,
        "extract_deadlines",
        lambda title, body, today: [
            ExtractedDeadline(date=when, what_en="Pay the exam fee", what_hi="परीक्षा शुल्क भरें", what_mr="परीक्षा शुल्क भरा"),
            ExtractedDeadline(date="2020-01-01", what_en="Old", what_hi="", what_mr=""),
        ],
    )
    n = office.post(
        f"{API}/notices", json={"title": "Exam fee", "body": "Pay the exam fee soon.", "audience": {"kind": "students"}}
    ).json()
    found = office.get(f"{API}/notices/{n['id']}/deadlines").json()
    assert [(d["date"], d["source"], d["what"]["hi"]) for d in found] == [(when, "ai", "परीक्षा शुल्क भरें")]


def test_unanswered_questions_become_faqs(client, sign_in, fees, db):  # noqa: F811
    office = new_client(client)
    sign_in(office, ["office"])
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    for q in (
        "Is there a canteen menu?",
        "is there a CANTEEN menu",
        "Is there a canteen menu ?!",
        "Where do I park my scooter?",
    ):
        assert student.post(f"{API}/assistant/ask", json={"question": q}).json()["grounded"] is False

    gaps = office.get(f"{API}/kb/gaps").json()
    assert [(g["key"], g["count"]) for g in gaps] == [("is there a canteen menu", 3), ("where do i park my scooter", 1)]
    home = office.get(f"{API}/dashboard").json()["help_desk"]
    assert home["unanswered"] == 2 and home["asked"] == 4 and home["top"][0]["count"] == 3

    faq = office.post(
        f"{API}/kb/gaps/answer",
        json={
            "key": gaps[0]["key"],
            "question": "Is there a canteen menu?",
            "answer": "The canteen menu is on the board near the library: poha, thali and tea.",
            "category": "hostel",
        },
    ).json()
    assert faq["title"] == "FAQ: Is there a canteen menu?" and faq["questions_closed"] == 3
    answer = student.post(f"{API}/assistant/ask", json={"question": "Is there a canteen menu?"}).json()
    assert answer["grounded"] and answer["sources"][0]["title"] == "FAQ: Is there a canteen menu?"
    assert office.post(f"{API}/kb/gaps/dismiss", json={"key": gaps[1]["key"]}).json() == {"questions_closed": 1}
    assert office.get(f"{API}/kb/gaps").json() == []
    assert student.get(f"{API}/kb/gaps").status_code == 403
    assert (
        "help_desk" not in office.get(f"{API}/dashboard").json()
        or office.get(f"{API}/dashboard").json()["help_desk"]["unanswered"] == 0
    )
