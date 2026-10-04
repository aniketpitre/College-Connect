"""
Receipt cancellations and refunds (spec §3.4): Accounts asks, the Principal approves, and only
then is a reversal posted. A receipt is never edited or deleted; a cancelled receipt stays in the
books marked CANCELLED and the Verify page says so.
"""

from datetime import UTC, datetime
from typing import Any

from pymongo.client_session import ClientSession

from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.core.money import format_inr
from app.modules.fees import approvals, ledger
from app.modules.fees.receipts import MODES, get_receipt
from app.modules.fees.schemas import RefundRequest
from app.modules.fees.service import find, oid
from app.modules.setup import service as setup
from app.modules.students import service as students


def request_cancel(ctx: AuthContext, receipt_id: str, reason: str, ip: str) -> dict[str, Any]:
    receipt = get_receipt(receipt_id)
    if receipt["status"] != "valid":
        raise AppError(409, "This receipt is already cancelled.", "conflict")
    student = students.get_student(receipt["student_id"])
    return approvals.create(
        ctx,
        kind="receipt_cancel",
        student=student,
        academic_year_id=receipt["academic_year_id"],
        amount=receipt["amount"],
        reason=reason,
        details={"receipt_id": receipt["_id"], "receipt_number": receipt["number"]},
        ip=ip,
        open_key=f"cancel:{receipt['_id']}",
    )


def _apply_cancel(ctx: AuthContext, approval: dict[str, Any], session: ClientSession, ip: str) -> dict[str, Any]:
    db = get_db()
    receipt = db.receipts.find_one_and_update(
        {"_id": approval["details"]["receipt_id"], "status": "valid"},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": datetime.now(UTC),
                "cancel_reason": approval["reason"],
                "cancelled_by": ctx.user_id,
                "cancel_approval_id": approval["_id"],
            }
        },
        session=session,
    )
    if not receipt:
        raise AppError(409, "This receipt is already cancelled.", "conflict")
    payment = db.ledger_entries.find_one({"_id": receipt["entry_id"]}, session=session)
    assert payment is not None
    entry = ledger.post(
        student_id=payment["student_id"],
        academic_year_id=payment["academic_year_id"],
        type="reversal",
        lines=[{"head_id": ln["head_id"], "amount": -ln["amount"]} for ln in payment["lines"]],
        created_by=ctx.user_id,
        session=session,
        ref={"type": "receipt", "id": receipt["_id"]},
        reason=f"Receipt {receipt['number']} cancelled: {approval['reason']}",
        reverses=payment["_id"],
        receipt_number=receipt["number"],
    )
    db.ledger_entries.update_one({"_id": payment["_id"]}, {"$set": {"reversed": True}}, session=session)
    return entry


def request_refund(ctx: AuthContext, body: RefundRequest, ip: str) -> dict[str, Any]:
    student = students.get_student(oid(body.student_id, "Student"))
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )
    balance = sum(e["amount"] for e in ledger.entries(student["_id"], year["_id"]))
    credit = -balance
    if credit <= 0:
        raise AppError(409, "The student has no credit to refund for this year.", "no_credit")
    if body.amount > credit:
        raise AppError(422, f"The student's credit is only {format_inr(credit)}.", field="amount")
    if body.mode != "cash" and not body.reference.strip():
        raise AppError(422, "Enter the reference for this payment mode.", field="reference")
    return approvals.create(
        ctx,
        kind="refund",
        student=student,
        academic_year_id=year["_id"],
        amount=body.amount,
        reason=body.reason,
        details={"mode": body.mode, "mode_label": MODES[body.mode], "reference": body.reference.strip()},
        ip=ip,
    )


def _apply_refund(ctx: AuthContext, approval: dict[str, Any], session: ClientSession, ip: str) -> dict[str, Any]:
    rows = ledger.entries(approval["student_id"], approval["academic_year_id"], session=session)
    credit = -sum(e["amount"] for e in rows)
    if approval["amount"] > credit:
        raise AppError(
            409, "The student's credit is now smaller than this refund. Reject it and ask again.", "conflict"
        )
    # Pay the credit back on the heads that were overpaid.
    lines = []
    left = approval["amount"]
    for head, amount in ledger.by_head(rows).items():
        if left and amount < 0:
            take = min(-amount, left)
            lines.append({"head_id": head, "amount": take})
            left -= take
    if left:
        lines.append({"head_id": rows[0]["lines"][0]["head_id"], "amount": left})
    return ledger.post(
        student_id=approval["student_id"],
        academic_year_id=approval["academic_year_id"],
        type="refund",
        lines=lines,
        created_by=ctx.user_id,
        session=session,
        ref={"type": "approval", "id": approval["_id"]},
        reason=f"Refund by {approval['details']['mode_label']}"
        + (f" ({approval['details']['reference']})" if approval["details"].get("reference") else "")
        + f": {approval['reason']}",
    )


approvals.HANDLERS["receipt_cancel"] = _apply_cancel
approvals.HANDLERS["refund"] = _apply_refund


def verify(code: str) -> dict[str, Any]:
    """What the public Verify page shows about a receipt: enough to check it, no more."""
    receipt = get_db().receipts.find_one({"verify_code": code.strip().upper()})
    if not receipt:
        raise AppError(404, "No receipt with this code. Check the code or ask the college office.", "not_found")
    name_parts = receipt["student"]["name"].split()
    masked_name = " ".join([name_parts[0], *(p[0] + "." for p in name_parts[1:])])
    prn = receipt["student"]["prn"]
    return {
        "type": "receipt",
        "valid": receipt["status"] == "valid",
        "status": receipt["status"],
        "number": receipt["number"],
        "date": receipt["collected_at"].isoformat(),
        "amount": receipt["amount"],
        "academic_year": receipt["academic_year"],
        "student_name": masked_name,
        "prn": prn[:-3] + "***" if len(prn) > 4 else "***",
        "college": setup.institution().get("name") or "",
        "cancelled_at": receipt["cancelled_at"].isoformat() if receipt.get("cancelled_at") else None,
    }
