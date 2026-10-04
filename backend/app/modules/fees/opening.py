"""
Opening balances (plan item 1.11): fees students already paid this year before the college
started using CollegeConnect, and dues carried over from earlier years.

Same pattern as the student import: upload a file, every row is checked, nothing is saved unless
the whole file is clean, then everything is saved in one transaction. A student's opening
balance can be imported only once per academic year.
"""

import csv
import io
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, run_in_transaction
from app.core.errors import AppError
from app.core.money import to_paise
from app.modules.fees import ledger
from app.modules.students.importer import read_rows

COLUMNS = ["prn", "paid", "old_receipt_no", "previous_dues", "note"]
EXAMPLE = {
    "prn": "2026BCA001",
    "paid": "13000",
    "old_receipt_no": "1452",
    "previous_dues": "0",
    "note": "Paid at counter in June",
}


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow(EXAMPLE)
    return out.getvalue()


def _previous_dues_head() -> ObjectId:
    head = get_db().fee_heads.find_one_and_update(
        {"code": "PREV"},
        {"$setOnInsert": {"name": "Previous years' dues", "status": "active", "created_at": datetime.now(UTC)}},
        upsert=True,
        return_document=True,
    )
    assert head is not None
    return head["_id"]


def _amount(text: str, column: str, errors: list[dict[str, Any]], line: int, prn: str) -> int:
    if not text.strip():
        return 0
    try:
        value = to_paise(text)
    except ValueError as e:
        errors.append({"row": line, "field": column, "message": str(e), "prn": prn})
        return 0
    if value < 0:
        errors.append({"row": line, "field": column, "message": "Must not be negative.", "prn": prn})
    return value


def run(ctx: AuthContext, year_id: ObjectId, filename: str, data: bytes, commit: bool, ip: str) -> dict[str, Any]:
    db = get_db()
    year = db.academic_years.find_one({"_id": year_id})
    if not year:
        raise AppError(404, "Academic year not found.")
    rows = read_rows(filename, data, required=("prn", "paid"))
    by_prn = {s["prn"]: s for s in db.students.find({"prn": {"$in": [r.get("prn", "").strip().upper() for r in rows]}})}
    done = {
        e["student_id"]
        for e in db.ledger_entries.find(
            {"academic_year_id": year_id, "type": {"$in": ["opening_paid", "opening_due"]}}, {"student_id": 1}
        )
    }
    errors: list[dict[str, Any]] = []
    plan: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for i, row in enumerate(rows):
        line = i + 2
        prn = row.get("prn", "").strip().upper()
        student = by_prn.get(prn)
        if not student:
            errors.append({"row": line, "field": "prn", "message": "No student with this PRN.", "prn": prn or None})
            continue
        if prn in seen:
            errors.append({"row": line, "field": "prn", "message": f"Same PRN as row {seen[prn]}.", "prn": prn})
            continue
        seen[prn] = line
        if student["_id"] in done:
            errors.append(
                {"row": line, "field": "prn", "message": "Opening balance already imported for this year.", "prn": prn}
            )
            continue
        before = len(errors)
        paid = _amount(row.get("paid", ""), "paid", errors, line, prn)
        dues = _amount(row.get("previous_dues", ""), "previous_dues", errors, line, prn)
        if len(errors) > before:
            continue
        if not paid and not dues:
            errors.append(
                {"row": line, "field": "paid", "message": "Enter an amount paid or previous dues.", "prn": prn}
            )
            continue
        plan.append(
            {
                "line": line,
                "student": student,
                "paid": paid,
                "dues": dues,
                "old_receipt": row.get("old_receipt_no", "").strip(),
                "note": row.get("note", "").strip(),
            }
        )

    # Paid amounts need this year's fee to be charged first (so they can be split over fee heads).
    accounts = {}
    for p in plan:
        if p["paid"]:
            entries = ledger.entries(p["student"]["_id"], year_id)
            balance = sum(e["amount"] for e in entries)
            if not any(e["type"] == "demand" for e in entries):
                errors.append(
                    {
                        "row": p["line"],
                        "field": "paid",
                        "message": "Charge this year's fee first (Fee setup).",
                        "prn": p["student"]["prn"],
                    }
                )
            elif p["paid"] > balance + p["dues"]:
                errors.append(
                    {
                        "row": p["line"],
                        "field": "paid",
                        "message": f"More than the {balance / 100:.2f} due.",
                        "prn": p["student"]["prn"],
                    }
                )
            accounts[p["student"]["_id"]] = entries
    errors.sort(key=lambda e: (e["row"], e["field"]))
    report = {
        "total": len(rows),
        "valid": len(plan)
        if not errors
        else len(plan) - len({e["row"] for e in errors if e["row"] in {p["line"] for p in plan}}),
        "paid": sum(p["paid"] for p in plan),
        "dues": sum(p["dues"] for p in plan),
        "errors": errors[:300],
        "error_count": len(errors),
        "committed": False,
    }
    if not commit or errors:
        return report

    prev_head = _previous_dues_head() if any(p["dues"] for p in plan) else None

    def work(session) -> None:
        for p in plan:
            sid = p["student"]["_id"]
            reason = (
                " · ".join(x for x in (f"Old receipt {p['old_receipt']}" if p["old_receipt"] else "", p["note"]) if x)
                or None
            )
            if p["dues"]:
                assert prev_head is not None
                ledger.post(
                    student_id=sid,
                    academic_year_id=year_id,
                    type="opening_due",
                    lines=[{"head_id": prev_head, "amount": p["dues"]}],
                    created_by=ctx.user_id,
                    session=session,
                    reason=reason,
                    opening_key=f"{sid}:{year_id}:due",
                )
            if p["paid"]:
                entries = accounts[sid]
                outstanding = ledger.by_head(entries)
                if p["dues"] and prev_head is not None:
                    outstanding[prev_head] = outstanding.get(prev_head, 0) + p["dues"]
                order = ledger.head_order(entries) + ([prev_head] if prev_head else [])
                ledger.post(
                    student_id=sid,
                    academic_year_id=year_id,
                    type="opening_paid",
                    lines=ledger.allocate(p["paid"], outstanding, order),
                    created_by=ctx.user_id,
                    session=session,
                    reason=reason,
                    opening_key=f"{sid}:{year_id}:paid",
                )
        audit.record(
            "fees.opening.imported",
            actor_id=ctx.user_id,
            ip=ip,
            session=session,
            details={
                "academic_year": year["name"],
                "students": len(plan),
                "paid": report["paid"],
                "dues": report["dues"],
            },
        )

    try:
        run_in_transaction(work)
    except DuplicateKeyError as e:
        raise AppError(
            409, "Someone imported opening balances for some of these students at the same time.", "conflict"
        ) from e
    report["committed"] = True
    return report
