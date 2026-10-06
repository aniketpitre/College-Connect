"""
Collecting a fee at the counter and the receipt it produces (spec §3.2 rules 3–5).

One transaction does everything: take the next receipt number from the year's counter →
insert the receipt → post the payment to the ledger → write the audit entry. If any step fails
the whole thing is undone, including the counter, so receipt numbers are sequential with no
gaps even with several cashiers at once (concurrent writers to the counter conflict and the
transaction is retried). Receipts are never edited or deleted.
"""

import secrets
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.client_session import ClientSession

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.email import send_email
from app.core.errors import AppError
from app.core.money import format_inr
from app.core.ratelimit import hit
from app.modules.fees import ledger
from app.modules.fees.schemas import CollectIn
from app.modules.fees.service import find, oid
from app.modules.setup import service as setup
from app.modules.students import service as students

IST = ZoneInfo("Asia/Kolkata")
MODES = {
    "cash": "Cash",
    "upi": "UPI",
    "card": "Card",
    "cheque": "Cheque",
    "dd": "Demand draft",
    "bank_transfer": "Bank transfer",
    "online": "Online payment",
}
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

register_indexes(
    "receipts",
    [
        IndexModel([("number", ASCENDING)], unique=True),
        IndexModel([("verify_code", ASCENDING)], unique=True),
        IndexModel([("collected_at", DESCENDING)]),
        IndexModel([("student_id", ASCENDING), ("collected_at", DESCENDING)]),
    ],
)


def new_verify_code() -> str:
    """12 characters, no look-alikes (0/O, 1/I): printed on the receipt and in its QR link."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(12))


def verify_url(base: str, code: str) -> str:
    return f"{base.rstrip('/')}/verify/{code}"


def view(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["_id"]),
        "number": r["number"],
        "academic_year": r["academic_year"],
        "academic_year_id": str(r["academic_year_id"]),
        "student_id": str(r["student_id"]),
        "student": r["student"],
        "amount": r["amount"],
        "lines": [{"code": ln["code"], "name": ln["name"], "amount": ln["amount"]} for ln in r["lines"]],
        "mode": r["mode"],
        "mode_label": MODES.get(r["mode"], r["mode"]),
        "reference": r.get("reference", ""),
        "bank": r.get("bank", ""),
        "instrument_date": r.get("instrument_date"),
        "note": r.get("note", ""),
        "collected_by": r["collector_name"],
        "collected_at": r["collected_at"].isoformat(),
        "status": r["status"],
        "cancelled_at": r["cancelled_at"].isoformat() if r.get("cancelled_at") else None,
        "cancel_reason": r.get("cancel_reason"),
        "prints": r.get("prints", 0),
        "verify_code": r["verify_code"],
    }


def collect(ctx: AuthContext, body: CollectIn, ip: str) -> dict[str, Any]:
    student = students.get_student(oid(body.student_id, "Student"))
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )

    def work(session: ClientSession) -> dict[str, Any]:
        return issue(
            student,
            year,
            body.amount,
            mode=body.mode,
            reference=body.reference,
            bank=body.bank.strip(),
            instrument_date=body.instrument_date.isoformat() if body.instrument_date else None,
            note=body.note.strip(),
            collector_id=ctx.user_id,
            collector_name=ctx.user["name"],
            ip=ip,
            session=session,
        )

    return view(run_in_transaction(work))


def issue(
    student: dict[str, Any],
    year: dict[str, Any],
    amount: int,
    *,
    mode: str,
    reference: str,
    collector_id: ObjectId | None,
    collector_name: str,
    ip: str | None,
    session: ClientSession,
    bank: str = "",
    instrument_date: str | None = None,
    note: str = "",
    allow_credit: bool = False,
) -> dict[str, Any]:
    """Inside a transaction: next receipt number, the receipt, the ledger payment and the audit entry.

    The counter refuses more than is due; an online payment the gateway has already taken is
    recorded in full (`allow_credit`): anything above the balance stays as a credit.
    """
    db = get_db()
    prefix = setup.institution().get("receipt_prefix") or "R"
    heads = {h["_id"]: h for h in db.fee_heads.find(session=session)}
    snapshot = students.summary(student)
    rows = ledger.entries(student["_id"], year["_id"], session=session)
    balance = sum(e["amount"] for e in rows)
    if not allow_credit:
        if balance <= 0:
            raise AppError(409, "Nothing is due for this year.", "nothing_due")
        if amount > balance:
            raise AppError(422, f"Only {format_inr(balance)} is due.", field="amount")
    counter = db.counters.find_one_and_update(
        {"_id": f"receipt:{year['name']}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    assert counter is not None  # upsert always returns the document
    seq = counter["seq"]
    number = f"{prefix}/{year['name']}/{seq:06d}"
    outstanding = ledger.by_head(rows)
    order = ledger.head_order(rows)
    if not order and not outstanding:  # an online payment with nothing demanded: a credit on the first head
        first = db.fee_heads.find_one({}, sort=[("_id", 1)], session=session)
        if first is None:
            raise AppError(409, "No fee heads are set up.", "nothing_due")
        order = [first["_id"]]
    lines = ledger.allocate(amount, outstanding, order)
    now = datetime.now(UTC)
    receipt: dict[str, Any] = {
        "number": number,
        "seq": seq,
        "academic_year_id": year["_id"],
        "academic_year": year["name"],
        "student_id": student["_id"],
        "student": {
            "name": student["name"],
            "prn": student["prn"],
            "class": " ".join(
                x for x in (snapshot["programme_code"], snapshot["year_label"], snapshot["division"]) if x
            ),
        },
        "amount": amount,
        "lines": [
            {
                "head_id": ln["head_id"],
                "code": heads[ln["head_id"]]["code"],
                "name": heads[ln["head_id"]]["name"],
                "amount": -ln["amount"],
            }
            for ln in lines
        ],
        "mode": mode,
        "reference": reference,
        "bank": bank,
        "instrument_date": instrument_date,
        "note": note,
        "collected_by": collector_id,
        "collector_name": collector_name,
        "collected_at": now,
        "status": "valid",
        "prints": 0,
        "verify_code": new_verify_code(),
    }
    receipt["_id"] = db.receipts.insert_one(receipt, session=session).inserted_id
    entry = ledger.post(
        student_id=student["_id"],
        academic_year_id=year["_id"],
        type="payment",
        lines=lines,
        created_by=collector_id,
        session=session,
        ref={"type": "receipt", "id": receipt["_id"]},
        receipt_number=number,
    )
    db.receipts.update_one({"_id": receipt["_id"]}, {"$set": {"entry_id": entry["_id"]}}, session=session)
    receipt["entry_id"] = entry["_id"]
    audit.record(
        "fees.collected",
        actor_id=collector_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"receipt": number, "amount": amount, "mode": mode},
        session=session,
    )
    return receipt


def get_receipt(receipt_id: str) -> dict[str, Any]:
    r = get_db().receipts.find_one({"_id": oid(receipt_id, "Receipt")})
    if not r:
        raise AppError(404, "Receipt not found.")
    return r


def take_print(receipt_id: str) -> tuple[dict[str, Any], bool]:
    """Counts a print; returns the receipt and whether this is the first (original) print."""
    r = get_db().receipts.find_one_and_update(
        {"_id": oid(receipt_id, "Receipt")}, {"$inc": {"prints": 1}}, return_document=ReturnDocument.BEFORE
    )
    if not r:
        raise AppError(404, "Receipt not found.")
    return r, r.get("prints", 0) == 0


def ist_day_range(day: str | None) -> tuple[datetime, datetime]:
    """A calendar day in India as a UTC range."""
    d = datetime.fromisoformat(day).date() if day else datetime.now(IST).date()
    start = datetime.combine(d, time.min, tzinfo=IST)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def list_receipts(
    *, date_from: str | None, date_to: str | None, student_id: str | None, number: str | None, limit: int = 500
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if student_id:
        query["student_id"] = oid(student_id, "Student")
    if number:
        text = number.strip().upper()
        query["number"] = text if "/" in text else {"$regex": f"/{int(text):06d}$"} if text.isdigit() else text
    if date_from or date_to:
        start = ist_day_range(date_from)[0] if date_from else datetime(2000, 1, 1, tzinfo=UTC)
        end = ist_day_range(date_to)[1] if date_to else datetime.now(UTC) + timedelta(days=1)
        query["collected_at"] = {"$gte": start, "$lt": end}
    rows = get_db().receipts.find(query).sort("collected_at", DESCENDING).limit(limit)
    return [view(r) for r in rows]


def today(day: str | None = None) -> dict[str, Any]:
    start, end = ist_day_range(day)
    db = get_db()
    rows = list(db.receipts.find({"collected_at": {"$gte": start, "$lt": end}}))
    valid = [r for r in rows if r["status"] == "valid"]
    by_mode: dict[str, int] = {}
    for r in valid:
        by_mode[r["mode"]] = by_mode.get(r["mode"], 0) + r["amount"]
    return {
        "date": start.astimezone(IST).date().isoformat(),
        "total": sum(r["amount"] for r in valid),
        "count": len(valid),
        "cancelled": len(rows) - len(valid),
        "by_mode": [
            {"mode": m, "label": MODES[m], "amount": a} for m, a in sorted(by_mode.items(), key=lambda x: -x[1])
        ],
        "pending_approvals": db.approvals.count_documents({"status": "pending"}),
    }


def email_receipt(ctx: AuthContext, receipt_id: str, base_url: str, ip: str) -> dict[str, Any]:
    r = get_receipt(receipt_id)
    student = students.get_student(r["student_id"])
    if not student.get("email"):
        raise AppError(409, "This student has no email address on record.", "no_email")
    hit(f"receipt-email:{receipt_id}", limit=3, window_seconds=3600)
    college = setup.institution().get("name") or "CollegeConnect"
    lines = "\n".join(f"  {ln['name']}: {format_inr(ln['amount'])}" for ln in r["lines"])
    sent = send_email(
        student["email"],
        f"Fee receipt {r['number']}",
        f"Dear {student['name']},\n\n{college} has received {format_inr(r['amount'])} "
        f"({MODES.get(r['mode'], r['mode'])}) towards your fees for {r['academic_year']}.\n\n"
        f"Receipt number: {r['number']}\n{lines}\n\n"
        f"Check this receipt online: {verify_url(base_url, r['verify_code'])}\n"
        "You can download it from CollegeConnect (Fees).\n",
    )
    if not sent:
        raise AppError(503, "The email could not be sent. Try again later.", "email_failed")
    audit.record(
        "fees.receipt.emailed",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=r["student_id"],
        ip=ip,
        details={"receipt": r["number"]},
    )
    return {"sent_to": student["email"]}
