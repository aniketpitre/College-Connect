from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from bson import ObjectId

from app.core import email
from app.core.config import settings
from app.modules.messaging import reminders
from app.modules.messaging import service as messaging
from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"


def _student(db, prn="2026BCA001"):
    return db.students.find_one({"prn": prn})


def _parent(db, student, **extra):
    return db.users.insert_one(
        {"kind": "parent", "name": "Suresh Patil", "roles": ["parent"], "status": "active", "phone": "9876500001",
         "contact_email": "suresh@example.com", "children": [{"student_id": student["_id"], "relation": "Father"}],
         "created_at": datetime.now(UTC), **extra}
    ).inserted_id  # fmt: skip


def test_student_and_parents_by_consent_and_preferences(fees, db):  # noqa: F811
    s = _student(db)
    db.students.update_one({"_id": s["_id"]}, {"$set": {"email": "rohan@example.com", "dob": "2005-01-01"}})
    s = _student(db)
    _parent(db, s, language="mr")
    email.OUTBOX.clear()
    assert messaging.notify(s, "results_published", {"exam": "Oct 2026"}) == 2
    to = {m.to: m for m in email.OUTBOX}
    assert "Results of Oct 2026 for Rohan Patil are out" in to["rohan@example.com"].text
    assert "निकाल" in to["suresh@example.com"].subject  # the parent reads Marathi

    # The adult student stops sharing results: parents don't hear about them, but still about certificates.
    db.students.update_one({"_id": s["_id"]}, {"$set": {"parent_access": {"results": False}}})
    s = _student(db)
    assert [u["kind"] for u in messaging.recipients(s, "results_published")] == ["student"]
    assert len(messaging.recipients(s, "certificate_ready")) == 2

    # Email switched off (SMS isn't set up): nothing is sent, and nothing is logged as failed.
    db.users.update_one({"_id": s["user_id"]}, {"$set": {"notify": {"email": False, "sms": True, "whatsapp": True}}})
    email.OUTBOX.clear()
    assert messaging.notify(s, "results_published", {"exam": "X"}) == 0 and email.OUTBOX == []
    assert db.message_log.count_documents({"status": "sent", "channel": "email"}) == 2


def test_sms_through_the_provider_with_dlt_templates(monkeypatch, fees, db):  # noqa: F811
    monkeypatch.setattr(messaging, "settings", replace(settings, sms_api_key="k"))
    s = _student(db)
    db.students.update_one({"_id": s["_id"]}, {"$set": {"phone": "9811111111"}})
    s = _student(db)
    sent = []

    class Ok:
        def raise_for_status(self):
            return None

    monkeypatch.setattr(messaging.httpx, "post", lambda url, **kw: sent.append((url, kw)) or Ok())
    # No DLT template configured: logged as failed, not sent.
    assert messaging.notify(s, "fee_overdue", {"amount": "₹5,000.00"}) == 0
    assert db.message_log.find_one({"channel": "sms"})["status"] == "failed"
    monkeypatch.setenv("SMS_TEMPLATE_FEE_OVERDUE", "tmpl-1")
    assert messaging.notify(s, "fee_overdue", {"amount": "₹5,000.00"}) == 1
    url, kw = sent[-1]
    assert "msg91" in url and kw["json"]["template_id"] == "tmpl-1"
    assert kw["json"]["recipients"] == [{"mobiles": "919811111111", "var1": "Rohan Patil", "var2": "₹5,000.00"}]
    assert db.message_log.find_one({"channel": "sms", "status": "sent"})["to"] == "••••••1111"


def test_fee_reminders_before_and_after_the_due_date(client, sign_in, fees, db):  # noqa: F811
    accounts = new_client(client)
    sign_in(accounts, ["accounts"])
    first = date.today() + timedelta(days=10)
    accounts.post(f"{API}/fees/structures", json=structure_body(fees, due_first=first))
    accounts.post(
        f"{API}/fees/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    db.students.update_many({}, {"$set": {"email": "x@example.com"}})
    assert reminders.queue_fee_reminders(first - timedelta(days=3)) == {"due": 3, "overdue": 0}
    assert reminders.queue_fee_reminders(first - timedelta(days=3)) == {"due": 0, "overdue": 0}  # once
    assert reminders.queue_fee_reminders(first - timedelta(days=2)) == {"due": 0, "overdue": 0}
    # Rohan pays the first installment; the others are reminded after the due date.
    accounts.post(
        f"{API}/fees/collect",
        json={
            "student_id": fees["students"]["2026BCA001"],
            "academic_year_id": fees["year"],
            "amount": 13_000 * RS,
            "mode": "cash",
        },
    )
    assert reminders.queue_fee_reminders(first + timedelta(days=1)) == {"due": 0, "overdue": 2}
    email.OUTBOX.clear()
    done = messaging.process_queue()
    assert done["processed"] == 5 and done["waiting"] == 0
    assert any("is overdue" in m.text and "₹13,000.00" in m.text for m in email.OUTBOX)


def test_settings_log_and_send_now(client, sign_in, fees, db):  # noqa: F811
    st = new_client(client)
    sign_in_as_student(st, db, "2026BCA001")
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"email": "rohan@example.com"}})
    mine = st.get(f"{API}/me/notifications").json()["channels"]
    assert [(c["channel"], c["on"], c["available"]) for c in mine] == [
        ("email", True, True),
        ("sms", True, False),
        ("whatsapp", True, False),
    ]
    assert mine[0]["to"] == "ro•••@example.com"
    assert st.put(f"{API}/me/notifications", json={"email": False, "sms": False, "whatsapp": False}).status_code == 422
    assert (
        st.put(f"{API}/me/notifications", json={"email": True, "sms": False, "whatsapp": True}).json()["channels"][1][
            "on"
        ]
        is False
    )

    messaging.queue(ObjectId(fees["students"]["2026BCA001"]), "results_published", {"exam": "Oct 2026"})
    office, faculty = new_client(client), new_client(client)
    sign_in(office, ["office"])
    sign_in(faculty, ["faculty"])
    assert faculty.get(f"{API}/messages/log").status_code == 403
    assert office.get(f"{API}/messages/log").json()["waiting"] == 1
    assert office.post(f"{API}/messages/queue/run").json() == {"processed": 1, "sent": 1, "waiting": 0}
    log = office.get(f"{API}/messages/log", params={"student_id": fees["students"]["2026BCA001"]}).json()["messages"]
    assert [(m["to_name"], m["template_label"], m["channel"], m["status"]) for m in log] == [
        ("Rohan Patil", "Results published", "email", "sent")
    ]
