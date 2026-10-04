"""
The student's own portal (spec R13): home cards, fees, receipts and the fee statement.

Every function starts from `students.my_student(ctx)`, so a student can only ever reach their
own record; ids from the request are always checked against it.
"""

from datetime import date, timedelta
from typing import Any

from bson import ObjectId

from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.modules.fees import ledger
from app.modules.fees import receipts as receipts_mod
from app.modules.fees import service as fees
from app.modules.notices import service as notices
from app.modules.students import service as students

DUE_SOON_DAYS = 15


def _years_for(student: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    ids = set(db.ledger_entries.distinct("academic_year_id", {"student_id": student["_id"]}))
    current = db.academic_years.find_one({"is_current": True})
    if current:
        ids.add(current["_id"])
    rows = db.academic_years.find({"_id": {"$in": list(ids)}}).sort("name", -1)
    return [{"id": str(y["_id"]), "name": y["name"], "is_current": bool(y.get("is_current"))} for y in rows]


def _year(student: dict[str, Any], academic_year_id: str | None) -> ObjectId:
    years = _years_for(student)
    if academic_year_id:
        if academic_year_id not in {y["id"] for y in years}:
            raise AppError(404, "No fee account for that year.")
        return ObjectId(academic_year_id)
    if not years:
        raise AppError(404, "No fee account yet.", "no_fees")
    current = next((y for y in years if y["is_current"]), years[0])
    return ObjectId(current["id"])


def my_fees(ctx: AuthContext, academic_year_id: str | None) -> dict[str, Any]:
    student = students.my_student(ctx)
    years = _years_for(student)
    year_id = _year(student, academic_year_id)
    account = fees.account(student["_id"], year_id)
    rows = get_db().receipts.find({"student_id": student["_id"], "academic_year_id": year_id}).sort("collected_at", -1)
    return {
        "years": years,
        "academic_year_id": str(year_id),
        **{
            k: account[k]
            for k in (
                "balance",
                "demand",
                "charges",
                "paid",
                "concessions",
                "scholarships",
                "refunds",
                "overdue",
                "installments",
                "by_head",
                "entries",
                "has_demand",
            )
        },
        "receipts": [
            {
                k: v
                for k, v in receipts_mod.view(r).items()
                if k in {"id", "number", "amount", "mode_label", "reference", "collected_at", "status"}
            }
            for r in rows
        ],
    }


def my_receipt(ctx: AuthContext, receipt_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    receipt = receipts_mod.get_receipt(receipt_id)
    if receipt["student_id"] != student["_id"]:
        raise AppError(404, "Receipt not found.")  # not 403: don't reveal other students' receipts
    return receipt


def statement(ctx: AuthContext, academic_year_id: str | None) -> tuple[dict[str, Any], str, dict[str, Any]]:
    student = students.my_student(ctx)
    year_id = _year(student, academic_year_id)
    year = get_db().academic_years.find_one({"_id": year_id})
    assert year is not None
    summary = students.summary(student)
    info = {
        "name": student["name"],
        "prn": student["prn"],
        "class": " ".join(x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x),
    }
    return info, year["name"], fees.account(student["_id"], year_id)


def home(ctx: AuthContext) -> dict[str, Any]:
    """Things that need the student's attention, most urgent first, plus a few figures."""
    student = students.my_student(ctx)
    db = get_db()
    cards: list[dict[str, Any]] = []
    balance = None
    current = db.academic_years.find_one({"is_current": True})
    if current:
        rows = ledger.entries(student["_id"], current["_id"])
        if rows:
            info = ledger.summary(rows)
            balance = info["balance"]
            if info["overdue"] > 0:
                first = next(i for i in info["installments"] if i["overdue"])
                cards.append(
                    {"kind": "fee_overdue", "severity": "danger", "amount": info["overdue"], "since": first["due_date"]}
                )
            else:
                soon = date.today() + timedelta(days=DUE_SOON_DAYS)
                upcoming = next((i for i in info["installments"] if i["due"] > 0), None)
                if upcoming and date.fromisoformat(upcoming["due_date"]) <= soon:
                    cards.append(
                        {
                            "kind": "fee_due_soon",
                            "severity": "warning",
                            "amount": upcoming["due"],
                            "due_date": upcoming["due_date"],
                            "label": upcoming["label"],
                        }
                    )
    for d in student.get("documents", []):
        if d["status"] == "rejected":
            cards.append(
                {"kind": "document_rejected", "severity": "warning", "type": d["type"], "reason": d.get("reason")}
            )
    recent = date.today() - timedelta(days=14)
    for r in db.student_change_requests.find(
        {"student_id": student["_id"], "status": {"$in": ["approved", "rejected"]}}
    ):
        if r.get("decided_at") and r["decided_at"].date() >= recent:
            cards.append(
                {
                    "kind": f"correction_{r['status']}",
                    "severity": "info",
                    "fields": sorted(r["changes"]),
                    "reason": r.get("decision_reason"),
                }
            )
    for n in notices.recent_for_student(ctx):
        cards.append(
            {
                "kind": "notice",
                "severity": "info",
                "notice_id": n["id"],
                "title": n["title"],
                "hi": n["hi"],
                "mr": n["mr"],
            }
        )
    summary = students.summary(student)
    return {
        "name": student["name"],
        "prn": student["prn"],
        "class": " · ".join(x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x),
        "academic_year": current["name"] if current else None,
        "photo_url": f"/files/{student['photo_file_id']}" if student.get("photo_file_id") else None,
        "balance": balance,
        "cards": cards,
    }
