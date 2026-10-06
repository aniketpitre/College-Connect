import re

from app.core import email
from tests.admissions_fixtures import API, PDF, apply, cycle, fill  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_payments import SECRET, _sig, gw  # noqa: F401
from tests.test_students import college  # noqa: F401


def test_cycle_options_and_enquiries(cycle, client, sign_in):  # noqa: F811
    opts = new_client(client).get(f"{API}/admissions/options").json()
    assert [c["name"] for c in opts["cycles"]] == ["Admissions 2026-27"]
    prog = opts["cycles"][0]["programmes"][0]
    assert prog["code"] == "BCA" and prog["seats"] == 3 and prog["reserved"][0]["code"] == "OBC"
    assert "refund_rules" not in opts["cycles"][0]  # internal

    bad = {**cycle["body"], "programmes": [{**cycle["body"]["programmes"][0], "reserved": {cycle["obc"]: 9}}]}
    assert cycle["cell"].post(f"{API}/admissions/cycles", json=bad).status_code == 422
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    assert faculty.get(f"{API}/admissions/cycles").status_code == 403

    public = new_client(client)
    assert public.post(
        f"{API}/admissions/enquiries/public",
        json={"name": "Ravi", "phone": "9822000000", "programme_id": cycle["bca"], "message": "Fees?"},
    ).json() == {"ok": True}
    cell = cycle["cell"]
    e = cell.get(f"{API}/admissions/enquiries").json()[0]
    assert e["source"] == "website" and e["programme"] == "BCA"
    upd = cell.patch(
        f"{API}/admissions/enquiries/{e['id']}", json={"status": "contacted", "note": "Called, will visit Monday"}
    ).json()
    assert upd["status"] == "contacted" and upd["notes"][0]["by"] == "Kiran Kale"


def test_apply_submit_scrutiny_and_return(cycle, client, db):  # noqa: F811
    c = apply(client, cycle, "9811100001")
    a = c.get(f"{API}/me/application").json()
    assert a["status"] == "draft" and a["personal"]["name"] == "Asha Pawar" and a["fee"]["status"] == "unpaid"
    for path in ("/me/home", "/students", "/me/student"):
        assert c.get(f"{API}{path}").status_code == 403, path  # an applicant reaches only the application

    a = fill(c, cycle)
    assert a["programme_code"] == "BCA" and a["merit_score"] == 82.5 and len(a["documents"]) == 2
    r = c.post(f"{API}/me/application/submit")
    assert r.status_code == 422 and r.json()["error"]["field"] == "fee"

    cell = cycle["cell"]
    paid = cell.post(f"{API}/admissions/applications/{a['id']}/fee", json={"mode": "cash"}).json()
    assert paid["fee"]["status"] == "paid" and paid["fee"]["receipt_number"] == "APP/2026-27/00001"
    sub = c.post(f"{API}/me/application/submit").json()
    assert sub["status"] == "submitted" and sub["number"] == "A/2026-27/00001" and not sub["can_edit"]
    assert c.put(f"{API}/me/application", json={"name": "Other"}).status_code == 409

    # Scrutiny: documents first; a bad document sends it back to the applicant.
    assert (
        cell.post(f"{API}/admissions/applications/{a['id']}/decide", json={"action": "verify"}).json()["error"]["code"]
        == "documents_pending"
    )
    docs = cell.get(f"{API}/admissions/applications/{a['id']}").json()["documents"]
    cell.post(f"{API}/admissions/applications/{a['id']}/documents/{docs[0]['id']}/decide", json={"approve": True})
    cell.post(
        f"{API}/admissions/applications/{a['id']}/documents/{docs[1]['id']}/decide",
        json={"approve": False, "reason": "Blurred"},
    )
    email.OUTBOX.clear()
    back = cell.post(
        f"{API}/admissions/applications/{a['id']}/decide",
        json={"action": "return", "reason": "Upload a clear HSC marksheet"},
    )
    assert back.json()["status"] == "returned"
    assert "clear HSC marksheet" in email.OUTBOX[-1].text and email.OUTBOX[-1].to == "asha@example.com"

    c.post(
        f"{API}/me/application/documents",
        data={"type": "hsc_marksheet"},
        files={"file": ("hsc.pdf", PDF, "application/pdf")},
    )
    again = c.post(f"{API}/me/application/submit").json()
    assert again["status"] == "submitted" and again["number"] == "A/2026-27/00001"  # same number
    for d in cell.get(f"{API}/admissions/applications/{a['id']}").json()["documents"]:
        if d["status"] != "verified":
            cell.post(f"{API}/admissions/applications/{a['id']}/documents/{d['id']}/decide", json={"approve": True})
    assert (
        cell.post(f"{API}/admissions/applications/{a['id']}/decide", json={"action": "verify"}).json()["status"]
        == "verified"
    )
    listed = cell.get(f"{API}/admissions/applications", params={"status": "verified"}).json()
    assert [(x["name"], x["category"], x["fee"]) for x in listed] == [("Asha Pawar", "OPEN", "paid")]

    # Files: an applicant sees only their own uploads.
    url = c.get(f"{API}/me/application").json()["documents"][0]["url"]
    assert c.get(f"{API}{url}").status_code == 200
    other = apply(client, cycle, "9811100002", name="Ravi", email_addr="ravi@example.com")
    assert other.get(f"{API}{url}").status_code == 404


def test_sign_in_again_and_online_application_fee(cycle, gw, client, db):  # noqa: F811
    apply(client, cycle, "9811100003")
    # Later: sign in again with the mobile number only.
    c = new_client(client)
    email.OUTBOX.clear()
    assert c.post(f"{API}/apply/code", json={"phone": "9811100003"}).json() == {"sent": True}
    code = re.search(r"\b(\d{6})\b", email.OUTBOX[-1].subject).group(1)
    c.post(f"{API}/apply/verify", json={"phone": "9811100003", "code": code})
    order = c.post(f"{API}/me/application/fee").json()
    assert order["amount"] == 50_000 and order["description"] == "Application fee"
    p = gw["pay"](order["order_id"])
    r = c.post(
        f"{API}/me/application/fee/{order['id']}/confirm",
        json={
            "razorpay_payment_id": p["id"],
            "razorpay_signature": _sig(SECRET, f"{order['order_id']}|{p['id']}".encode()),
        },
    )
    fee = r.json()["fee"]
    assert fee["status"] == "paid" and fee["mode"] == "online" and fee["receipt_number"] == "APP/2026-27/00001"
    assert db.ledger_entries.count_documents({}) == 0  # not a student yet: no ledger
    assert c.post(f"{API}/me/application/fee").status_code == 409
