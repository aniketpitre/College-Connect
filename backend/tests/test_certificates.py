import io
from dataclasses import replace
from datetime import UTC, date, datetime

from bson import ObjectId
from pypdf import PdfReader

from app.core import email
from app.core.config import settings
from app.modules.certificates.service import add_working_days
from app.modules.jobs import router as jobs_router
from tests.academics_fixtures import API, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student


def test_working_days_skip_sundays_and_holidays(db):
    db.holidays.insert_one({"date": "2026-10-02", "name": "Gandhi Jayanti", "status": "active"})
    assert add_working_days(date(2026, 9, 30), 2) == date(2026, 10, 3)  # Thu 1, (Fri 2 holiday), Sat 3
    assert add_working_days(date(2026, 10, 3), 1) == date(2026, 10, 5)  # Sunday skipped


def _students(client, db, prns):
    out = {}
    for prn in prns:
        c = new_client(client)
        sign_in_as_student(c, db, prn)
        out[prn] = c
    return out


def test_bonafide_from_request_to_verified_pdf(monkeypatch, academics, client, db):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))  # Monday
    st = _students(client, db, ["2026BCA001", "2026BCA002"])
    rohan, neha, office = st["2026BCA001"], st["2026BCA002"], academics["office"]
    types = {t["type"]: t for t in rohan.get(f"{API}/me/certificates").json()["types"]}
    assert types["bonafide"]["promised_days"] == 2 and types["tc"]["signer"] == "principal"

    r = rohan.post(f"{API}/me/certificates", json={"type": "bonafide", "purpose": "Bank education loan"})
    assert r.status_code == 201 and r.json()["due_date"] == "2026-10-07" and r.json()["status"] == "requested"
    rid = r.json()["id"]
    assert rohan.post(f"{API}/me/certificates", json={"type": "bonafide", "purpose": "Again"}).status_code == 409
    assert rohan.post(f"{API}/me/certificates", json={"type": "noc", "purpose": "Internship"}).status_code == 422

    queue = office.get(f"{API}/certificates/requests", params={"status": "open"}).json()
    assert queue[0]["student"] == "Rohan Patil" and queue[0]["can"]["verify"]
    act = lambda c, a, **k: c.post(f"{API}/certificates/requests/{rid}/action", json={"action": a, **k})  # noqa: E731
    assert act(rohan, "verify").status_code == 403
    assert act(office, "issue").status_code == 403  # not signed yet
    assert act(office, "verify").json()["status"] == "verified"
    assert act(office, "sign").json()["status"] == "signed"
    issued = act(office, "issue").json()
    assert issued["status"] == "ready" and issued["number"] == "C/2026-27/00001"

    mine = rohan.get(f"{API}/me/certificates").json()["requests"][0]
    pdf = rohan.get(f"{API}/me/certificates/{rid}/pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert (
        "BONAFIDE CERTIFICATE" in text
        and "Rohan Patil" in text
        and "Bank education loan" in text
        and "Registrar" in text
    )
    assert mine["number"] == "C/2026-27/00001"
    assert neha.get(f"{API}/me/certificates/{rid}/pdf").status_code == 404
    cert = db.certificates.find_one({})
    v = client.get(f"{API}/verify/{cert['verify_code']}").json()
    assert v["type"] == "certificate" and v["valid"] and v["student_name"] == "Rohan P." and v["prn"] == "2026BCA***"
    assert client.get(f"{API}/verify/NOTACODE1234").status_code == 404

    # Reject needs a reason, and the student sees it.
    n = neha.post(f"{API}/me/certificates", json={"type": "character", "purpose": "Passport"}).json()["id"]
    assert office.post(f"{API}/certificates/requests/{n}/action", json={"action": "reject"}).status_code == 422
    office.post(f"{API}/certificates/requests/{n}/action", json={"action": "reject", "reason": "Ask your HOD first"})
    assert neha.get(f"{API}/me/certificates").json()["requests"][0]["reason"] == "Ask your HOD first"


def test_tc_needs_no_dues_and_principal_and_locks_the_account(monkeypatch, academics, client, db, sign_in):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))
    om = _students(client, db, ["2026BCA003"])["2026BCA003"]
    office = academics["office"]
    principal = new_client(client)
    sign_in(principal, ["principal"])
    sid = ObjectId(academics["students"]["2026BCA003"])
    year = db.academic_years.find_one()["_id"]
    head = db.fee_heads.insert_one({"code": "TUITION", "name": "Tuition", "status": "active"}).inserted_id
    db.ledger_entries.insert_one(
        {"student_id": sid, "academic_year_id": year, "type": "demand", "amount": 500_000,
         "lines": [{"head_id": head, "amount": 500_000}], "at": datetime.now(UTC), "created_by": None}
    )  # fmt: skip

    assert om.post(f"{API}/me/certificates", json={"type": "tc", "purpose": "Admission elsewhere"}).status_code == 422
    rid = om.post(
        f"{API}/me/certificates",
        json={"type": "tc", "purpose": "Admission elsewhere", "reason_for_leaving": "Moving to Pune"},
    ).json()["id"]
    act = lambda c, a, **k: c.post(f"{API}/certificates/requests/{rid}/action", json={"action": a, **k})  # noqa: E731
    blocked = act(office, "verify")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "dues_pending"
    assert office.get(f"{API}/certificates/requests").json()[0]["dues"][0]["amount"] == 500_000
    db.ledger_entries.insert_one(
        {"student_id": sid, "academic_year_id": year, "type": "payment", "amount": -500_000,
         "lines": [{"head_id": head, "amount": -500_000}], "at": datetime.now(UTC), "created_by": None}
    )  # fmt: skip
    assert act(office, "verify").json()["status"] == "verified"
    assert act(office, "sign").status_code == 403  # the Principal signs a TC
    assert principal.get(f"{API}/certificates/requests").json()[0]["can"]["sign"]
    assert act(principal, "sign").json()["status"] == "signed"
    assert act(principal, "issue").status_code == 403  # the office issues
    assert act(office, "issue").json()["status"] == "ready"

    assert db.students.find_one({"_id": sid})["status"] == "tc"
    blocked = om.post(f"{API}/me/certificates", json={"type": "character", "purpose": "Job"})
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "read_only"
    assert om.get(f"{API}/me/certificates").status_code == 200  # still reads
    text = "".join(
        p.extract_text() for p in PdfReader(io.BytesIO(om.get(f"{API}/me/certificates/{rid}/pdf").content)).pages
    )
    assert "TRANSFER CERTIFICATE" in text and "Moving to Pune" in text and "Principal" in text


def test_noc_is_signed_by_the_hod_and_overdue_requests_escalate(monkeypatch, academics, client, db, sign_in):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))
    neha = _students(client, db, ["2026BCA002"])["2026BCA002"]
    office, t = academics["office"], academics["teachers"]
    principal = new_client(client)
    sign_in(principal, ["principal"], email="principal@college.test")
    body = {
        "type": "noc",
        "purpose": "Summer internship",
        "organisation": "Infosys Pune",
        "from_date": "2026-11-01",
        "to_date": "2026-12-15",
    }
    rid = neha.post(f"{API}/me/certificates", json=body).json()["id"]
    office.post(f"{API}/certificates/requests/{rid}/action", json={"action": "verify"})
    assert t["comhod"]["client"].get(f"{API}/certificates/requests").json() == []
    assert (
        t["comhod"]["client"].post(f"{API}/certificates/requests/{rid}/action", json={"action": "sign"}).status_code
        == 403
    )
    assert (
        t["hod"]["client"].post(f"{API}/certificates/requests/{rid}/action", json={"action": "sign"}).json()["status"]
        == "signed"
    )

    late = neha.post(f"{API}/me/certificates", json={"type": "bonafide", "purpose": "Scholarship"}).json()
    at(monkeypatch, ist(date(2026, 10, 9), 9))
    assert office.get(f"{API}/certificates/requests", params={"status": "open"}).json()
    monkeypatch.setattr(jobs_router, "settings", replace(settings, cron_secret="s3cret"))
    assert client.get(f"{API}/cron/daily").status_code == 401
    email.OUTBOX.clear()
    ran = client.get(f"{API}/cron/daily", headers={"Authorization": "Bearer s3cret"}).json()
    assert ran["certificates"] == {"escalated": 2, "emailed": 1}  # the NOC (signed, not issued) is late too
    assert email.OUTBOX[-1].to == "principal@college.test" and "Neha Joshi" in email.OUTBOX[-1].text
    assert (
        client.get(f"{API}/cron/daily", headers={"Authorization": "Bearer s3cret"}).json()["certificates"]["escalated"]
        == 0
    )
    mine = {r["id"]: r for r in neha.get(f"{API}/me/certificates").json()["requests"]}
    assert mine[late["id"]]["overdue"] and mine[late["id"]]["escalated"]
