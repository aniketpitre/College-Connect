from datetime import UTC, date, datetime

from bson import ObjectId

from app.core import email
from app.modules.grievance import service as grievance
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"
DAY = date(2026, 10, 5)  # a Monday


def test_grievance_anonymity_sensitive_cases_feedback_and_escalation(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 10))
    rohan, neha = new_client(client), new_client(client)
    sign_in_as_student(rohan, db, "2026BCA001")
    sign_in_as_student(neha, db, "2026BCA002")
    sid = ObjectId(fees["students"]["2026BCA001"])
    db.students.update_one({"_id": sid}, {"$set": {"email": "rohan@example.com"}})
    db.users.insert_one(
        {
            "kind": "parent",
            "name": "Suresh Patil",
            "roles": ["parent"],
            "status": "active",
            "phone": "9876500001",
            "contact_email": "suresh@example.com",
            "children": [{"student_id": sid, "relation": "Father"}],
            "created_at": datetime.now(UTC),
        }
    )
    cell, principal, icc = new_client(client), new_client(client), new_client(client)
    sign_in(cell, ["grievance"])
    sign_in(principal, ["principal"])
    sign_in(icc, ["icc"])

    # Rohan complains about fees anonymously; due in 5 working days.
    g = rohan.post(
        f"{API}/me/grievances",
        json={
            "category": "fees",
            "subject": "Scholarship not credited",
            "text": "My MahaDBT amount is still not adjusted.",
            "anonymous": True,
        },
    ).json()
    assert g["number"] == "GRV/2026/00001" and g["status"] == "open" and g["due_date"] == "2026-10-10"
    entry = db.audit_log.find_one({"action": "grievance.raised"})
    assert entry.get("actor_id") is None  # not even the audit log names an anonymous student
    rows = cell.get(f"{API}/grievances").json()
    assert [r["number"] for r in rows] == ["GRV/2026/00001"] and rows[0]["student"] is None
    assert icc.get(f"{API}/grievances").json() == []  # the ICC sees sensitive cases only
    assert principal.get(f"{API}/grievances/{g['id']}").json()["can_act"] is False
    assert principal.post(f"{API}/grievances/{g['id']}/action", json={"action": "take"}).status_code == 403
    assert neha.get(f"{API}/me/grievances/{g['id']}").status_code == 404

    # A harassment complaint goes only to the ICC, which sees who raised it.
    h = neha.post(
        f"{API}/me/grievances",
        json={"category": "harassment", "subject": "Comments in class", "text": "A senior keeps passing comments."},
    ).json()
    assert h["sensitive"] is True
    assert cell.get(f"{API}/grievances/{h['id']}").status_code == 404
    assert principal.get(f"{API}/grievances/{h['id']}").status_code == 404
    seen = icc.get(f"{API}/grievances/{h['id']}").json()
    assert seen["student"]["prn"] == "2026BCA002" and seen["can_act"] is True
    assert {r["category"]: r["received"] for r in principal.get(f"{API}/grievances/stats").json()["by_category"]}[
        "harassment"
    ] == 1  # the Principal sees only counts

    # The cell replies (Rohan is told, not his father), keeps an internal note and resolves.
    email.OUTBOX.clear()
    cell.post(f"{API}/grievances/{g['id']}/action", json={"action": "reply", "text": "We have written to MahaDBT."})
    assert [m.to for m in email.OUTBOX] == ["rohan@example.com"]
    cell.post(f"{API}/grievances/{g['id']}/action", json={"action": "note", "text": "Accounts to follow up"})
    mine = rohan.get(f"{API}/me/grievances/{g['id']}").json()
    assert mine["status"] == "in_progress" and [e["kind"] for e in mine["history"]] == ["raised", "reply"]
    assert cell.post(f"{API}/grievances/{g['id']}/action", json={"action": "resolve"}).status_code == 422
    cell.post(f"{API}/grievances/{g['id']}/action", json={"action": "resolve", "text": "Amount adjusted on 6 Oct."})
    assert rohan.get(f"{API}/me/grievances").json()["grievances"][0]["status"] == "resolved"

    # Not satisfied: reopened once and escalated to the Principal straight away.
    db.users.update_many({"roles": "principal"}, {"$set": {"email": "principal@college.test"}})
    email.OUTBOX.clear()
    back = rohan.post(f"{API}/me/grievances/{g['id']}/feedback", json={"satisfied": False, "rating": 2}).json()
    assert back["status"] == "open" and back["escalated"] is True and back["reopened"] == 1
    assert [m.to for m in email.OUTBOX] == ["principal@college.test"]
    assert "Rohan" not in email.OUTBOX[0].text and "GRV/2026/00001" in email.OUTBOX[0].text
    cell.post(f"{API}/grievances/{g['id']}/action", json={"action": "resolve", "text": "Refund cheque issued."})
    done = rohan.post(
        f"{API}/me/grievances/{g['id']}/feedback", json={"satisfied": True, "rating": 4, "comment": "Thanks"}
    ).json()
    assert done["status"] == "closed" and done["feedback"]["rating"] == 4

    # The daily job escalates the overdue harassment case to the ICC and closes silent resolved ones.
    db.users.update_many({"roles": "icc"}, {"$set": {"email": "icc@college.test"}})
    c = rohan.post(
        f"{API}/me/grievances",
        json={
            "category": "library",
            "subject": "Reading room closed",
            "text": "The reading room is closed on Saturdays.",
        },
    ).json()
    cell.post(f"{API}/grievances/{c['id']}/action", json={"action": "resolve", "text": "Open on Saturdays from now."})
    at(monkeypatch, ist(date(2026, 10, 20), 9))
    email.OUTBOX.clear()
    out = grievance.daily()
    assert out == {"escalated": 1, "emailed": 1, "closed": 1}
    assert [m.to for m in email.OUTBOX] == ["icc@college.test"]
    assert icc.get(f"{API}/grievances?status=overdue").json()[0]["escalated"] is True
    assert rohan.get(f"{API}/me/grievances/{c['id']}").json()["status"] == "closed"
    assert grievance.daily()["escalated"] == 0  # once each

    stats = cell.get(f"{API}/grievances/stats").json()
    assert stats["received"] == 3 and stats["resolved"] == 2 and stats["satisfied"] == 1 and stats["overdue"] == 1
