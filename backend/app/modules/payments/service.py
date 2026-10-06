"""
Online fee payment (plan 3.2).

1. A student (or a parent who can see fees) chooses an amount; we record an `online_payments`
   document and create a gateway order for exactly that amount.
2. The browser pays through Razorpay Checkout and sends back the signed result. We check the
   signature, ask the gateway for the order's captured payment, and issue the receipt in the
   same transaction that marks the payment paid. A second confirmation (the webhook, or a
   double tap) finds it already paid, so one payment never makes two receipts.
3. If the browser closes before step 2, the signed webhook (`payment.captured`) or the daily job
   settles it the same way. Accounts can also check any pending payment by hand.

Money the gateway took is always recorded: if it is more than is now due (for example, the fee
was also paid at the counter), the extra stays as a credit in the ledger for a refund.
"""

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.money import format_inr
from app.core.ratelimit import hit
from app.modules.fees import ledger, receipts
from app.modules.fees.service import oid
from app.modules.payments import gateway
from app.modules.portal import service as portal
from app.modules.setup import service as setup
from app.modules.students import service as students

register_indexes(
    "online_payments",
    [
        IndexModel([("order_id", ASCENDING)], unique=True, partialFilterExpression={"order_id": {"$type": "string"}}),
        IndexModel(
            [("gateway_payment_id", ASCENDING)], partialFilterExpression={"gateway_payment_id": {"$type": "string"}}
        ),
        IndexModel([("status", ASCENDING), ("created_at", ASCENDING)]),
        IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
    ],
)

STATUS_LABELS = {
    "created": "Waiting for payment",
    "paid": "Paid",
    "failed": "Could not start",
    "expired": "Not paid",
    "mismatch": "Amount differs: check",
}
SETTLE_AFTER = timedelta(minutes=30)
GIVE_UP_AFTER = timedelta(days=3)


def view(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(p["_id"]),
        "purpose": p.get("purpose", "fees"),
        "student_id": str(p["student_id"]) if p.get("student_id") else None,
        "application_id": str(p["application_id"]) if p.get("application_id") else None,
        "student": p.get("student"),
        "academic_year": p.get("academic_year"),
        "amount": p["amount"],
        "status": p["status"],
        "status_label": STATUS_LABELS.get(p["status"], p["status"]),
        "order_id": p.get("order_id"),
        "gateway_payment_id": p.get("gateway_payment_id"),
        "method": p.get("method"),
        "receipt_id": str(p["receipt_id"]) if p.get("receipt_id") else None,
        "receipt_number": p.get("receipt_number"),
        "credit": p.get("credit", 0),
        "paid_by": p.get("payer_kind"),
        "created_at": p["created_at"].isoformat(),
        "paid_at": p["paid_at"].isoformat() if p.get("paid_at") else None,
        "settled_by": p.get("settled_by"),
        "last_error": p.get("last_error"),
    }


# --- the student or parent pays -------------------------------------------------------------


def start(ctx: AuthContext, academic_year_id: str | None, amount: int) -> dict[str, Any]:
    if not gateway.enabled():
        raise AppError(503, "Online payment isn't set up yet. Please pay at the college counter.", "payments_off")
    hit(f"pay:{ctx.user_id}", limit=10, window_seconds=60 * 60)
    student = students.my_student(ctx)
    year_id = portal._year(student, academic_year_id)
    year = get_db().academic_years.find_one({"_id": year_id})
    assert year is not None
    balance = sum(e["amount"] for e in ledger.entries(student["_id"], year_id))
    if balance <= 0:
        raise AppError(409, "Nothing is due for this year.", "nothing_due")
    if amount > balance:
        raise AppError(422, f"Only {format_inr(balance)} is due.", "too_much", "amount")
    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        "student_id": student["_id"],
        "student": {"name": student["name"], "prn": student["prn"]},
        "academic_year_id": year_id,
        "academic_year": year["name"],
        "amount": amount,
        "status": "created",
        "created_at": now,
        "created_by": ctx.user_id,
        "payer_kind": ctx.user.get("kind"),
    }
    return _open_order(
        doc,
        notes={"prn": student["prn"], "year": year["name"]},
        description=f"Fees {year['name']} · {student['prn']}",
        prefill={"name": student["name"], "email": student.get("email") or "", "contact": student.get("phone") or ""},
    )


def _open_order(
    doc: dict[str, Any], *, notes: dict[str, str], description: str, prefill: dict[str, str]
) -> dict[str, Any]:
    """Records the payment and creates the gateway order for exactly its amount."""
    db = get_db()
    doc["_id"] = db.online_payments.insert_one(doc).inserted_id
    try:
        order = gateway.create_order(doc["amount"], str(doc["_id"]), notes)
    except AppError as e:
        db.online_payments.update_one({"_id": doc["_id"]}, {"$set": {"status": "failed", "last_error": e.message}})
        raise
    db.online_payments.update_one({"_id": doc["_id"]}, {"$set": {"order_id": order["id"]}})
    college = setup.institution()
    return {
        "id": str(doc["_id"]),
        "order_id": order["id"],
        "key_id": gateway.settings.razorpay_key_id,
        "amount": doc["amount"],
        "currency": "INR",
        "name": college.get("name") or "CollegeConnect",
        "description": description,
        "prefill": prefill,
    }


def start_application_fee(ctx: AuthContext, application: dict[str, Any]) -> dict[str, Any]:
    """An admission applicant pays the application fee (no student record or ledger yet)."""
    if not gateway.enabled():
        raise AppError(503, "Online payment isn't set up yet. Please pay at the college office.", "payments_off")
    hit(f"pay:{ctx.user_id}", limit=10, window_seconds=60 * 60)
    p = application["personal"]
    doc: dict[str, Any] = {
        "purpose": "application",
        "application_id": application["_id"],
        "student_id": None,
        "student": {"name": p.get("name"), "prn": application.get("number") or "applicant"},
        "amount": application["fee"]["amount"],
        "status": "created",
        "created_at": datetime.now(UTC),
        "created_by": ctx.user_id,
        "payer_kind": "applicant",
    }
    return _open_order(
        doc,
        notes={"application": str(application["_id"])},
        description="Application fee",
        prefill={"name": p.get("name") or "", "email": p.get("email") or "", "contact": p.get("phone") or ""},
    )


def confirm_application_fee(
    application: dict[str, Any], payment_id: str, gateway_payment_id: str, signature: str, ip: str
) -> dict[str, Any]:
    p = get_db().online_payments.find_one({"_id": oid(payment_id, "Payment"), "application_id": application["_id"]})
    if not p:
        raise AppError(404, "Payment not found.")
    if p["status"] == "paid":
        return view(p)
    if not p.get("order_id") or not gateway.checkout_signature_ok(p["order_id"], gateway_payment_id, signature):
        raise AppError(400, "The payment could not be verified.", "bad_signature")
    return view(_check_gateway(p, source="checkout", ip=ip))


def _mine(ctx: AuthContext, payment_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    p = get_db().online_payments.find_one({"_id": oid(payment_id, "Payment"), "student_id": student["_id"]})
    if not p:
        raise AppError(404, "Payment not found.")
    return p


def confirm(ctx: AuthContext, payment_id: str, gateway_payment_id: str, signature: str, ip: str) -> dict[str, Any]:
    p = _mine(ctx, payment_id)
    if p["status"] == "paid":
        return view(p)
    if not p.get("order_id") or not gateway.checkout_signature_ok(p["order_id"], gateway_payment_id, signature):
        raise AppError(400, "The payment could not be verified.", "bad_signature")
    return view(_check_gateway(p, source="checkout", ip=ip))


# --- settling a payment (checkout, webhook, daily job, accounts) ----------------------------


def _captured(p: dict[str, Any]) -> dict[str, Any] | None:
    return next((x for x in gateway.order_payments(p["order_id"]) if x.get("status") == "captured"), None)


def _check_gateway(p: dict[str, Any], *, source: str, ip: str | None) -> dict[str, Any]:
    """Asks the gateway about the order and settles it if a payment was captured."""
    paid = _captured(p)
    if paid:
        return settle(p, paid, source=source, ip=ip)
    return p


def settle(p: dict[str, Any], payment: dict[str, Any], *, source: str, ip: str | None) -> dict[str, Any]:
    """Marks the payment paid and issues its receipt, once, in one transaction."""
    db = get_db()
    if payment.get("order_id") != p.get("order_id"):
        raise AppError(400, "The payment belongs to another order.", "bad_payment")
    if int(payment.get("amount", -1)) != p["amount"]:
        db.online_payments.update_one(
            {"_id": p["_id"], "status": "created"},
            {
                "$set": {
                    "status": "mismatch",
                    "gateway_payment_id": payment.get("id"),
                    "gateway_amount": payment.get("amount"),
                }
            },
        )
        audit.record(
            "payments.mismatch",
            target_type="student" if p.get("student_id") else "application",
            target_id=p.get("student_id") or p.get("application_id"),
            ip=ip,
        )
        return db.online_payments.find_one({"_id": p["_id"]}) or p

    def work(session: ClientSession) -> dict[str, Any]:
        current = db.online_payments.find_one({"_id": p["_id"]}, session=session)
        assert current is not None
        if current["status"] == "paid":
            return current
        if current.get("purpose") == "application":
            return _settle_application(current, payment, source, ip, session)
        student = students.get_student(current["student_id"], session=session)
        year = db.academic_years.find_one({"_id": current["academic_year_id"]}, session=session)
        assert year is not None
        due = sum(e["amount"] for e in ledger.entries(student["_id"], year["_id"], session=session))
        receipt = receipts.issue(
            student,
            year,
            current["amount"],
            mode="online",
            reference=str(payment.get("id")),
            note=str(payment.get("method") or ""),
            collector_id=None,
            collector_name="Online payment",
            ip=ip,
            session=session,
            allow_credit=True,
        )
        now = datetime.now(UTC)
        update = {
            "status": "paid",
            "gateway_payment_id": payment.get("id"),
            "method": payment.get("method"),
            "paid_at": now,
            "receipt_id": receipt["_id"],
            "receipt_number": receipt["number"],
            "settled_by": source,
            "credit": max(0, current["amount"] - max(due, 0)),
        }
        db.online_payments.update_one({"_id": current["_id"]}, {"$set": update}, session=session)
        audit.record(
            "payments.paid",
            actor_id=current.get("created_by"),
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            details={"receipt": receipt["number"], "amount": current["amount"], "via": source},
            session=session,
        )
        return {**current, **update}

    return run_in_transaction(work)


def _settle_application(
    current: dict[str, Any], payment: dict[str, Any], source: str, ip: str | None, session: ClientSession
) -> dict[str, Any]:
    from app.modules.admissions import service as admissions

    number = admissions.record_fee(
        current["application_id"], mode="online", reference=str(payment.get("id")), by=None, session=session
    )
    update = {
        "status": "paid",
        "gateway_payment_id": payment.get("id"),
        "method": payment.get("method"),
        "paid_at": datetime.now(UTC),
        "receipt_number": number,
        "settled_by": source,
    }
    get_db().online_payments.update_one({"_id": current["_id"]}, {"$set": update}, session=session)
    return {**current, **update}


def webhook(body: bytes, signature: str | None) -> dict[str, Any]:
    if not gateway.webhook_signature_ok(body, signature or ""):
        raise AppError(400, "Bad signature.", "bad_signature")
    event = json.loads(body)
    kind = event.get("event")
    payment = ((event.get("payload") or {}).get("payment") or {}).get("entity") or {}
    p = get_db().online_payments.find_one({"order_id": payment.get("order_id")}) if payment.get("order_id") else None
    if p is None:
        return {"ok": True, "ignored": True}  # not ours (another app on the same account), or a test ping
    if kind in ("payment.captured", "order.paid") and payment.get("status") == "captured":
        settle(p, payment, source="webhook", ip=None)
    elif kind == "payment.failed":
        reason = (payment.get("error_description") or "Payment failed")[:200]
        get_db().online_payments.update_one({"_id": p["_id"]}, {"$set": {"last_error": reason}})
    return {"ok": True}


def check(ctx: AuthContext, payment_id: str, ip: str) -> dict[str, Any]:
    p = get_db().online_payments.find_one({"_id": oid(payment_id, "Payment")})
    if not p:
        raise AppError(404, "Payment not found.")
    if p["status"] in ("created", "expired") and p.get("order_id"):
        if p["status"] == "expired":  # money can still arrive late; check again
            get_db().online_payments.update_one({"_id": p["_id"]}, {"$set": {"status": "created"}})
            p["status"] = "created"
        p = _check_gateway(p, source="accounts", ip=ip)
        audit.record(
            "payments.checked",
            actor_id=ctx.user_id,
            target_type="student" if p.get("student_id") else "application",
            target_id=p.get("student_id") or p.get("application_id"),
            ip=ip,
        )
    return view(p)


def daily_check(limit: int = 50) -> dict[str, int]:
    """Cron: settles payments whose browser never came back; gives up on old unpaid orders."""
    if not gateway.enabled():
        return {"checked": 0, "settled": 0, "expired": 0}
    db = get_db()
    now = datetime.now(UTC)
    expired = db.online_payments.update_many(
        {"status": "created", "created_at": {"$lt": now - GIVE_UP_AFTER}}, {"$set": {"status": "expired"}}
    ).modified_count
    settled = checked = 0
    for p in db.online_payments.find(
        {"status": "created", "order_id": {"$type": "string"}, "created_at": {"$lt": now - SETTLE_AFTER}}
    ).limit(limit):
        checked += 1
        try:
            if _check_gateway(p, source="daily check", ip=None)["status"] == "paid":
                settled += 1
        except AppError:
            break  # the gateway is down: try again tomorrow
    return {"checked": checked, "settled": settled, "expired": expired}


# --- accounts: the day's online payments and reconciliation ---------------------------------


def day_list(day: str | None) -> dict[str, Any]:
    start, end = receipts.ist_day_range(day)
    rows = list(get_db().online_payments.find({"created_at": {"$gte": start, "$lt": end}}).sort("created_at", -1))
    paid = [p for p in rows if p["status"] == "paid"]
    return {
        "day": start.astimezone(receipts.IST).date().isoformat(),
        "enabled": gateway.enabled(),
        "payments": [view(p) for p in rows],
        "paid_count": len(paid),
        "paid_amount": sum(p["amount"] for p in paid),
        "waiting": sum(1 for p in rows if p["status"] == "created"),
        "problems": sum(1 for p in rows if p["status"] in ("mismatch", "failed")),
    }


def _column(header: list[str], *names: str) -> int | None:
    norm = [h.strip().lower().replace(" ", "_") for h in header]
    return next((norm.index(n) for n in names if n in norm), None)


def reconcile(data: bytes) -> dict[str, Any]:
    """Matches the gateway's payments export (CSV) with what CollegeConnect recorded."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AppError(422, "Upload the CSV file exported from the gateway dashboard.", "bad_file", "file") from e
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise AppError(422, "The file is empty.", "bad_file", "file")
    header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    id_col = _column(header, "id", "payment_id")
    amount_col = _column(header, "amount")
    status_col = _column(header, "status")
    if id_col is None or amount_col is None:
        raise AppError(422, "The file needs payment id and amount columns.", "bad_file", "file")
    gateway_rows: dict[str, int] = {}
    for r in body:
        if status_col is not None and r[status_col].strip().lower() not in ("captured", "refunded"):
            continue
        try:
            rupees = float(r[amount_col].replace(",", "").strip())
        except (ValueError, IndexError):
            continue
        gateway_rows[r[id_col].strip()] = round(rupees * 100)
    ours = {
        p["gateway_payment_id"]: p
        for p in get_db().online_payments.find({"gateway_payment_id": {"$in": list(gateway_rows)}})
    }
    matched, differs, missing_here = [], [], []
    for pid, amount in gateway_rows.items():
        p = ours.get(pid)
        if p is None or p["status"] != "paid":
            missing_here.append({"gateway_payment_id": pid, "amount": amount, "payment": view(p) if p else None})
        elif p["amount"] != amount:
            differs.append({**view(p), "gateway_amount": amount})
        else:
            matched.append(view(p))
    # Our paid payments over the same days that the file doesn't list.
    days = [datetime.fromisoformat(m["paid_at"]) for m in matched + differs if m["paid_at"]]
    missing_there = []
    if days:
        lo, hi = min(days).replace(hour=0, minute=0, second=0), max(days) + timedelta(days=1)
        for p in get_db().online_payments.find({"status": "paid", "paid_at": {"$gte": lo, "$lt": hi}}):
            if p.get("gateway_payment_id") not in gateway_rows:
                missing_there.append(view(p))
    return {
        "rows": len(gateway_rows),
        "matched": len(matched),
        "matched_amount": sum(m["amount"] for m in matched),
        "amount_differs": differs,
        "missing_in_collegeconnect": missing_here,
        "missing_in_gateway_file": missing_there,
    }
