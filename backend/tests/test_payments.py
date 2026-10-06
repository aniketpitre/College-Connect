import hashlib
import hmac
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.core.config import settings
from app.modules.payments import gateway
from app.modules.payments import service as payments
from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"
SECRET, HOOK = "test-secret", "hook-secret"


def _sig(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


@pytest.fixture
def gw(monkeypatch):
    """A fake Razorpay: orders and their payments live in memory."""
    monkeypatch.setattr(
        gateway,
        "settings",
        replace(settings, razorpay_key_id="rzp_test_1", razorpay_key_secret=SECRET, razorpay_webhook_secret=HOOK),
    )
    state = {"orders": {}, "n": 0}

    def create_order(amount, receipt, notes):
        state["n"] += 1
        oid = f"order_{state['n']}"
        state["orders"][oid] = {"amount": amount, "payments": []}
        return {"id": oid, "amount": amount, "status": "created"}

    def pay(order_id, amount=None, status="captured"):
        p = {
            "id": f"pay_{order_id}",
            "order_id": order_id,
            "amount": amount or state["orders"][order_id]["amount"],
            "status": status,
            "method": "upi",
        }
        state["orders"][order_id]["payments"] = [p]
        return p

    monkeypatch.setattr(gateway, "create_order", create_order)
    monkeypatch.setattr(gateway, "order_payments", lambda order_id: state["orders"][order_id]["payments"])
    state["pay"] = pay
    return state


@pytest.fixture
def ready(client, sign_in, fees, db):  # noqa: F811
    accounts = new_client(client)
    sign_in(accounts, ["accounts"], name="Kavita Deshmukh")
    accounts.post(f"{API}/fees/structures", json=structure_body(fees))
    accounts.post(
        f"{API}/fees/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    return {"accounts": accounts, "student": student, **fees}


def _balance(db, fees, prn="2026BCA001"):  # noqa: F811
    return sum(e["amount"] for e in db.ledger_entries.find({"student_id": ObjectId(fees["students"][prn])}))


def test_switched_off_without_keys(ready):
    assert ready["student"].get(f"{API}/me/fees").json()["online_payment"] is False
    r = ready["student"].post(f"{API}/me/payments", json={"amount": 100 * RS})
    assert r.status_code == 503 and r.json()["error"]["code"] == "payments_off"


def test_checkout_issues_one_receipt(ready, gw, db):
    st = ready["student"]
    assert st.get(f"{API}/me/fees").json()["online_payment"] is True
    assert st.post(f"{API}/me/payments", json={"amount": 999_999 * RS}).status_code == 422  # more than is due
    order = st.post(f"{API}/me/payments", json={"amount": 5_000 * RS}).json()
    assert (
        order["key_id"] == "rzp_test_1" and order["amount"] == 5_000 * RS and order["prefill"]["name"] == "Rohan Patil"
    )
    before = _balance(db, ready)

    confirm = lambda pid, sig: st.post(  # noqa: E731
        f"{API}/me/payments/{order['id']}/confirm", json={"razorpay_payment_id": pid, "razorpay_signature": sig}
    )
    assert confirm("pay_x", "0" * 64).status_code == 400  # forged
    good = _sig(SECRET, f"{order['order_id']}|pay_{order['order_id']}".encode())
    assert confirm(f"pay_{order['order_id']}", good).json()["status"] == "created"  # not captured yet
    gw["pay"](order["order_id"])
    paid = confirm(f"pay_{order['order_id']}", good).json()
    assert paid["status"] == "paid" and paid["receipt_number"].endswith("/000001") and paid["settled_by"] == "checkout"
    assert confirm(f"pay_{order['order_id']}", good).json()["receipt_number"] == paid["receipt_number"]

    # The webhook for the same payment changes nothing.
    event = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": gw["orders"][order["order_id"]]["payments"][0]}},
    }
    body = json.dumps(event).encode()
    hook = new_client(ready["student"])
    assert (
        hook.post(f"{API}/payments/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": "bad"}).status_code
        == 400
    )
    assert hook.post(
        f"{API}/payments/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": _sig(HOOK, body)}
    ).json() == {"ok": True}
    assert db.receipts.count_documents({}) == 1
    receipt = db.receipts.find_one({})
    assert (
        receipt["mode"] == "online"
        and receipt["reference"] == f"pay_{order['order_id']}"
        and receipt["collected_by"] is None
    )
    assert _balance(db, ready) == before - 5_000 * RS
    assert st.get(f"{API}/me/fees").json()["receipts"][0]["mode_label"] == "Online payment"


def test_webhook_settles_when_the_browser_closed(ready, gw, db):
    st = ready["student"]
    order = st.post(f"{API}/me/payments", json={"amount": 2_000 * RS}).json()
    p = gw["pay"](order["order_id"])
    body = json.dumps({"event": "order.paid", "payload": {"payment": {"entity": p}}}).encode()
    r = new_client(st).post(
        f"{API}/payments/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": _sig(HOOK, body)}
    )
    assert r.status_code == 200
    doc = db.online_payments.find_one({"order_id": order["order_id"]})
    assert doc["status"] == "paid" and doc["settled_by"] == "webhook"

    # A captured amount that differs from the order is never receipted automatically.
    other = st.post(f"{API}/me/payments", json={"amount": 1_000 * RS}).json()
    bad = gw["pay"](other["order_id"], amount=10 * RS)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": bad}}}).encode()
    new_client(st).post(
        f"{API}/payments/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": _sig(HOOK, body)}
    )
    assert db.online_payments.find_one({"order_id": other["order_id"]})["status"] == "mismatch"
    assert db.receipts.count_documents({}) == 1


def test_paid_at_the_counter_meanwhile_leaves_a_credit(ready, gw, db):
    st, accounts = ready["student"], ready["accounts"]
    due = _balance(db, ready)
    order = st.post(f"{API}/me/payments", json={"amount": due}).json()
    accounts.post(
        f"{API}/fees/collect",
        json={
            "student_id": ready["students"]["2026BCA001"],
            "academic_year_id": ready["year"],
            "amount": 1_000 * RS,
            "mode": "cash",
        },
    )
    p = gw["pay"](order["order_id"])
    st.post(
        f"{API}/me/payments/{order['id']}/confirm",
        json={
            "razorpay_payment_id": p["id"],
            "razorpay_signature": _sig(SECRET, f"{order['order_id']}|{p['id']}".encode()),
        },
    )
    doc = db.online_payments.find_one({"_id": ObjectId(order["id"])})
    assert doc["status"] == "paid" and doc["credit"] == 1_000 * RS
    assert _balance(db, ready) == -1_000 * RS  # in credit, for a refund


def test_daily_check_list_and_reconcile(ready, gw, db):
    st, accounts = ready["student"], ready["accounts"]
    a = st.post(f"{API}/me/payments", json={"amount": 3_000 * RS}).json()
    b = st.post(f"{API}/me/payments", json={"amount": 1_000 * RS}).json()
    c = st.post(f"{API}/me/payments", json={"amount": 500 * RS}).json()
    old = datetime.now(UTC) - timedelta(hours=1)
    db.online_payments.update_many({}, {"$set": {"created_at": old}})
    db.online_payments.update_one({"_id": ObjectId(c["id"])}, {"$set": {"created_at": old - timedelta(days=4)}})
    gw["pay"](a["order_id"])
    assert payments.daily_check() == {"checked": 2, "settled": 1, "expired": 1}

    day = accounts.get(f"{API}/fees/online-payments").json()
    assert day["paid_count"] == 1 and day["paid_amount"] == 3_000 * RS and day["waiting"] == 1
    assert accounts.get(f"{API}/fees/online-payments", params={"day": "2020-01-01"}).json()["payments"] == []
    gw["pay"](b["order_id"])
    assert accounts.post(f"{API}/fees/online-payments/{b['id']}/check").json()["status"] == "paid"
    assert st.post(f"{API}/fees/online-payments/{b['id']}/check").status_code == 403

    csv = (
        "id,amount,currency,status,order_id\n"
        f"pay_{a['order_id']},3000.00,INR,captured,{a['order_id']}\n"
        "pay_unknown,250,INR,captured,order_x\n"
        "pay_fail,99,INR,failed,order_y\n"
    )
    report = accounts.post(
        f"{API}/fees/online-payments/reconcile", files={"file": ("payments.csv", csv.encode(), "text/csv")}
    ).json()
    assert report["rows"] == 2 and report["matched"] == 1 and report["matched_amount"] == 3_000 * RS
    assert [m["gateway_payment_id"] for m in report["missing_in_collegeconnect"]] == ["pay_unknown"]
    assert [m["gateway_payment_id"] for m in report["missing_in_gateway_file"]] == [f"pay_{b['order_id']}"]


def test_parents_can_pay_if_fees_are_shared(ready, gw, client, db, sign_in):
    sid = ObjectId(ready["students"]["2026BCA001"])
    parent = new_client(client)
    user = sign_in(parent, ["parent"], kind="parent", name="Suresh Patil")
    db.users.update_one({"_id": user["_id"]}, {"$set": {"children": [{"student_id": sid, "relation": "Father"}]}})
    assert parent.post(f"{API}/me/payments", json={"amount": 100 * RS}).status_code == 201
    db.students.update_one({"_id": sid}, {"$set": {"parent_access": {"fees": False}}})
    assert parent.post(f"{API}/me/payments", json={"amount": 100 * RS}).json()["error"]["code"] == "not_shared"
