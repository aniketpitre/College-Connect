"""
Each student's fee account (spec §3.2 money rules).

A student's balance is the SUM of their ledger entries; it is never stored or edited. Entries
are never changed or deleted: a mistake is corrected by a reversal entry that points at it.

amount > 0 → the student owes more (demand, charge, opening due, refund paid out, reversal of a
payment); amount < 0 → owes less (payment, concession, scholarship, opening paid).
Each entry also has `lines` per fee head (summing to `amount`) for head-wise reports.
"""

from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.client_session import ClientSession

from app.core.db import get_db, register_indexes

register_indexes(
    "ledger_entries",
    [
        IndexModel([("student_id", ASCENDING), ("academic_year_id", ASCENDING), ("at", ASCENDING)]),
        IndexModel([("type", ASCENDING), ("at", ASCENDING)]),
        # One fee demand per student per academic year.
        IndexModel(
            [("demand_key", ASCENDING)], unique=True, partialFilterExpression={"demand_key": {"$type": "string"}}
        ),
        # One opening balance (paid / previous dues) per student per year.
        IndexModel(
            [("opening_key", ASCENDING)], unique=True, partialFilterExpression={"opening_key": {"$type": "string"}}
        ),
        # A payment/credit can be reversed only once.
        IndexModel([("reverses", ASCENDING)], unique=True, partialFilterExpression={"reverses": {"$type": "objectId"}}),
    ],
)

DEBIT_TYPES = {"demand", "charge", "opening_due", "refund"}
CREDIT_TYPES = {"payment", "concession", "scholarship", "opening_paid"}
LABELS = {
    "demand": "Fee for the year",
    "charge": "Charge",
    "opening_due": "Previous dues",
    "refund": "Refund paid",
    "payment": "Payment",
    "concession": "Concession",
    "scholarship": "Scholarship",
    "opening_paid": "Paid before CollegeConnect",
    "reversal": "Reversal",
}


def post(
    *,
    student_id: ObjectId,
    academic_year_id: ObjectId,
    type: str,
    lines: list[dict[str, Any]],
    created_by: ObjectId | None,
    session: ClientSession,
    ref: dict[str, Any] | None = None,
    reason: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Adds one entry. `lines` are [{head_id, amount}] with the entry's sign already applied."""
    lines = [ln for ln in lines if ln["amount"]]
    entry = {
        "student_id": student_id,
        "academic_year_id": academic_year_id,
        "type": type,
        "amount": sum(ln["amount"] for ln in lines),
        "lines": lines,
        "at": datetime.now(UTC),
        "created_by": created_by,
        **({"ref": ref} if ref else {}),
        **({"reason": reason} if reason else {}),
        **extra,
    }
    entry["_id"] = get_db().ledger_entries.insert_one(entry, session=session).inserted_id
    return entry


def entries(student_id: ObjectId, academic_year_id: ObjectId | None = None, session: ClientSession | None = None):
    query: dict[str, Any] = {"student_id": student_id}
    if academic_year_id:
        query["academic_year_id"] = academic_year_id
    return list(get_db().ledger_entries.find(query, session=session).sort("at", ASCENDING))


def by_head(rows: list[dict[str, Any]]) -> dict[ObjectId, int]:
    """Outstanding per fee head (positive = still owed)."""
    totals: dict[ObjectId, int] = {}
    for e in rows:
        for ln in e["lines"]:
            totals[ln["head_id"]] = totals.get(ln["head_id"], 0) + ln["amount"]
    return totals


def allocate(amount: int, outstanding: dict[ObjectId, int], order: list[ObjectId]) -> list[dict[str, Any]]:
    """Splits a credit of `amount` paise over the heads still owed, in `order` (fee structure order).
    Returns negative lines. Anything left over (shouldn't happen: callers cap at the balance) goes
    to the first head."""
    lines = []
    left = amount
    for head in order + [h for h in outstanding if h not in order]:
        owed = outstanding.get(head, 0)
        if left <= 0 or owed <= 0:
            continue
        take = min(owed, left)
        lines.append({"head_id": head, "amount": -take})
        left -= take
    if left > 0:
        first = order[0] if order else next(iter(outstanding), None)
        if first is None:
            raise ValueError("Nothing to allocate against")
        lines.append({"head_id": first, "amount": -left})
    return lines


def head_order(rows: list[dict[str, Any]]) -> list[ObjectId]:
    """Fee heads in the order the year's demand lists them (payments clear them in this order)."""
    order: list[ObjectId] = []
    for e in rows:
        for ln in e["lines"]:
            if ln["head_id"] not in order:
                order.append(ln["head_id"])
    return order


def summary(rows: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    """Totals, installments and what is overdue, from a student's entries for one year."""
    today = today or date.today()
    total = {t: 0 for t in (*DEBIT_TYPES, *CREDIT_TYPES, "reversal")}
    for e in rows:
        total[e["type"]] = total.get(e["type"], 0) + e["amount"]
    balance = sum(e["amount"] for e in rows)
    demand = next((e for e in rows if e["type"] == "demand"), None)
    installments = []
    credits = -sum(e["amount"] for e in rows if e["amount"] < 0) - sum(
        e["amount"] for e in rows if e["type"] in {"reversal", "refund"} and e["amount"] > 0
    )
    # Credits clear installments in date order.
    remaining_credit = max(credits - sum(e["amount"] for e in rows if e["type"] in {"opening_due", "charge"}), 0)
    overdue = 0
    for inst in (demand or {}).get("installments", []):
        paid = min(inst["amount"], remaining_credit)
        remaining_credit -= paid
        due_left = inst["amount"] - paid
        is_overdue = due_left > 0 and date.fromisoformat(inst["due_date"]) < today
        overdue += due_left if is_overdue else 0
        installments.append({**inst, "paid": paid, "due": due_left, "overdue": is_overdue})
    return {
        "balance": balance,
        "demand": total["demand"],
        "charges": total["charge"] + total["opening_due"],
        "paid": -(total["payment"] + total["opening_paid"]),
        "concessions": -total["concession"],
        "scholarships": -total["scholarship"],
        "refunds": total["refund"],
        "reversals": total["reversal"],
        "installments": installments,
        "overdue": overdue,
        "late_fee": (demand or {}).get("late_fee", 0),
    }
