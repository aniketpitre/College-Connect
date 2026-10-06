import re
from datetime import date

from bson import ObjectId

from app.core import email
from tests.academics_fixtures import API, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

PHONE = "9876500001"


def _otp_sign_in(client, phone=PHONE):
    parent = new_client(client)
    email.OUTBOX.clear()
    assert parent.post(f"{API}/auth/otp/request", json={"phone": f"+91 {phone}"}).json() == {"sent": True}
    code = re.search(r"\b(\d{6})\b", email.OUTBOX[-1].subject).group(1)
    assert (
        parent.post(
            f"{API}/auth/otp/verify", json={"phone": phone, "code": "000000" if code != "000000" else "111111"}
        ).status_code
        == 401
    )
    r = parent.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200 and r.json()["kind"] == "parent", r.text
    return parent


def test_office_links_parents_and_consent_for_minors(monkeypatch, academics, client, db):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))
    st, office = academics["students"], academics["office"]
    db.students.update_one({"_id": ObjectId(st["2026BCA001"])}, {"$set": {"dob": "2007-03-01"}})  # 19
    db.students.update_one({"_id": ObjectId(st["2026BCA002"])}, {"$set": {"dob": "2009-01-15"}})  # 17
    body = {"name": "Suresh Patil", "phone": PHONE, "email": "suresh@example.com", "relation": "Father"}

    r = office.post(f"{API}/students/{st['2026BCA001']}/parents", json=body)
    assert r.status_code == 201 and r.json()["parents"][0]["relation"] == "Father" and not r.json()["minor"]
    assert office.post(f"{API}/students/{st['2026BCA001']}/parents", json=body).status_code == 409  # already linked
    minor = office.post(f"{API}/students/{st['2026BCA002']}/parents", json=body)
    assert minor.status_code == 422 and minor.json()["error"]["code"] == "consent_required"
    ok = office.post(f"{API}/students/{st['2026BCA002']}/parents", json={**body, "consent": True}).json()
    assert ok["minor"] and ok["consent_recorded"] and ok["parents"][0]["children"] == 2  # same account, two children
    assert db.users.count_documents({"kind": "parent"}) == 1

    taken = office.post(f"{API}/students/{st['2026BCA003']}/parents", json={**body, "phone": "9812345678"})
    assert taken.status_code == 201
    rao = academics["teachers"]["rao"]["client"]
    assert rao.post(f"{API}/students/{st['2026BCA003']}/parents", json=body).status_code == 403


def test_parent_sees_only_their_children_and_what_is_shared(monkeypatch, academics, client, db):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))
    st, office = academics["students"], academics["office"]
    rohan, neha, om = st["2026BCA001"], st["2026BCA002"], st["2026BCA003"]
    db.students.update_one({"_id": ObjectId(rohan)}, {"$set": {"dob": "2007-03-01"}})
    db.students.update_one({"_id": ObjectId(neha)}, {"$set": {"dob": "2009-01-15"}})
    body = {
        "name": "Suresh Patil",
        "phone": PHONE,
        "email": "suresh@example.com",
        "relation": "Father",
        "consent": True,
    }
    for sid in (rohan, neha):
        office.post(f"{API}/students/{sid}/parents", json=body)

    # Unknown numbers get the same answer and no email.
    email.OUTBOX.clear()
    assert new_client(client).post(f"{API}/auth/otp/request", json={"phone": "9000000000"}).json() == {"sent": True}
    assert email.OUTBOX == []

    parent = _otp_sign_in(client)
    kids = parent.get(f"{API}/parent/children").json()
    assert [k["name"] for k in kids] == ["Rohan Patil", "Neha Joshi"] and kids[0]["access"]["results"]
    assert parent.get(f"{API}/me/home").json()["error"]["code"] == "choose_child"
    as_rohan = {"X-Child": rohan}
    assert parent.get(f"{API}/me/home", headers=as_rohan).json()["name"] == "Rohan Patil"
    assert parent.get(f"{API}/me/home", headers={"X-Child": om}).status_code == 404  # not their child
    assert parent.get(f"{API}/me/attendance", headers=as_rohan).status_code == 200
    assert parent.get(f"{API}/notices", headers=as_rohan).status_code == 200

    # Nothing outside the allow-list: the student's own pages, writes, staff pages.
    for path in ("/me/student", "/me/data-export", "/me/parent-access", "/students", "/dashboard"):
        assert parent.get(f"{API}{path}", headers=as_rohan).status_code == 403, path
    assert parent.post(f"{API}/me/student/change-requests", json={}, headers=as_rohan).status_code == 403

    # Rohan (19) stops sharing marks and results; Neha (17) can't.
    rohan_c, neha_c = new_client(client), new_client(client)
    sign_in_as_student(rohan_c, db, "2026BCA001")
    sign_in_as_student(neha_c, db, "2026BCA002")
    mine = rohan_c.get(f"{API}/me/parent-access").json()
    assert mine["can_change"] and mine["parents"] == [{"name": "Suresh Patil", "relation": "Father"}]
    off = {"fees": True, "attendance": True, "results": False}
    assert rohan_c.put(f"{API}/me/parent-access", json=off).json()["access"] == off
    assert neha_c.put(f"{API}/me/parent-access", json=off).status_code == 409
    for path in ("/me/results", "/me/marks", "/me/exams"):
        r = parent.get(f"{API}{path}", headers=as_rohan)
        assert r.status_code == 403 and r.json()["error"]["code"] == "not_shared", path
    assert parent.get(f"{API}/me/results", headers={"X-Child": neha}).status_code == 200
    rohan_c.put(f"{API}/me/parent-access", json={"fees": False, "attendance": False, "results": True})
    home = parent.get(f"{API}/me/home", headers=as_rohan).json()
    assert home["balance"] is None and home["attendance"] is None

    # Unlinking the last child closes the parent account and signs it out.
    accounts = db.users.find_one({"kind": "parent"})
    for sid in (rohan, neha):
        office.delete(f"{API}/students/{sid}/parents/{accounts['_id']}")
    assert db.users.find_one({"_id": accounts["_id"]})["status"] == "disabled"
    assert parent.get(f"{API}/parent/children").status_code == 401


def test_parent_can_ask_for_a_certificate_and_set_a_password(monkeypatch, academics, client, db):  # noqa: F811
    at(monkeypatch, ist(date(2026, 10, 5), 11))
    rohan = academics["students"]["2026BCA001"]
    academics["office"].post(
        f"{API}/students/{rohan}/parents",
        json={"name": "Suresh Patil", "phone": PHONE, "email": "suresh@example.com"},
    )
    parent = _otp_sign_in(client)
    r = parent.post(f"{API}/me/certificates", json={"type": "bonafide", "purpose": "Bank loan"})  # only child
    assert r.status_code == 201, r.text
    assert db.certificate_requests.find_one({})["student_id"] == ObjectId(rohan)

    # "Forgot password" works by mobile number and mails the contact email; then password sign-in works.
    email.OUTBOX.clear()
    new_client(client).post(f"{API}/auth/password/forgot", json={"identifier": PHONE})
    assert email.OUTBOX[-1].to == "suresh@example.com"
    token = email.OUTBOX[-1].text.split("#", 1)[1].split()[0]
    assert (
        new_client(client)
        .post(f"{API}/auth/password/reset", json={"token": token, "new_password": "Monsoon-Garden-42"})
        .status_code
        == 200
    )
    login = new_client(client).post(f"{API}/auth/login", json={"identifier": PHONE, "password": "Monsoon-Garden-42"})
    assert login.status_code == 200 and login.json()["kind"] == "parent"
