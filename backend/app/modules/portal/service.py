"""
The student's own portal (spec R13): home cards, fees, receipts and the fee statement.

Every function starts from `students.my_student(ctx)`, so a student can only ever reach their
own record; ids from the request are always checked against it.
"""

from datetime import date, timedelta
from typing import Any

from bson import ObjectId

from app.core import clock
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.modules.attendance import stats
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
    from app.modules.payments import gateway

    return {
        "years": years,
        "academic_year_id": str(year_id),
        "online_payment": gateway.enabled(),
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


CARD_AREA = {
    "fee_overdue": "fees",
    "fee_due_soon": "fees",
    "attendance_low": "attendance",
    "attendance_warning": "attendance",
    "exam_form": "results",
    "hall_ticket": "results",
    "results": "results",
}
STUDENT_ONLY = {"document_rejected", "correction_approved", "correction_rejected", "exam_form"}


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
                soon = clock.today() + timedelta(days=DUE_SOON_DAYS)
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
    attendance = stats.student_summary(student)
    low = [
        x
        for x in attendance["subjects"]
        if x["status"] in ("critical", "warning") and x["held"] >= stats.ALERT_MIN_LECTURES
    ]
    for x in sorted(low, key=lambda x: x["percent"] or 0)[:3]:
        cards.append(
            {
                "kind": "attendance_low" if x["status"] == "critical" else "attendance_warning",
                "severity": "danger" if x["status"] == "critical" else "warning",
                "code": x["code"],
                "percent": x["percent"],
                "minimum": attendance["minimum"],
                "must_attend": x["must_attend"],
                "can_miss": x["can_miss"],
            }
        )
    for d in student.get("documents", []):
        if d["status"] == "rejected":
            cards.append(
                {"kind": "document_rejected", "severity": "warning", "type": d["type"], "reason": d.get("reason")}
            )
    recent = clock.today() - timedelta(days=14)
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
    from app.modules.exams import service as exams

    for x in exams.my_exams(ctx):
        if x["form_open"] and x["form_status"] in ("not_submitted", "rejected"):
            cards.append(
                {"kind": "exam_form", "severity": "warning", "title": x["name"], "due_date": x["form_deadline"]}
            )
        if x["hall_ticket"]:
            cards.append({"kind": "hall_ticket", "severity": "info", "title": x["name"]})
    recent_results = clock.today() - timedelta(days=14)
    for s in db.exam_sessions.find(
        {"results_published": True, "results_published_at": {"$exists": True}}, {"name": 1, "results_published_at": 1}
    ):
        if s["results_published_at"].date() >= recent_results and db.results.find_one(
            {"session_id": s["_id"], "student_id": student["_id"]}, {"_id": 1}
        ):
            cards.append({"kind": "results", "severity": "info", "title": s["name"]})
    for r in db.certificate_requests.find({"student_id": student["_id"], "status": "ready"}):
        if r.get("issued_at") and r["issued_at"].date() >= recent_results:
            cards.append({"kind": "certificate_ready", "severity": "info", "type": r["type"]})
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
    attendance_pct = attendance["overall"]["percent"]
    if ctx.user.get("kind") == "parent":
        # Parents see only what the student shares, and not the student's own to-dos.
        from app.modules.parents import service as parents

        shared = parents.access(student)
        cards = [c for c in cards if c["kind"] not in STUDENT_ONLY and shared.get(CARD_AREA.get(c["kind"], ""), True)]
        balance = balance if shared["fees"] else None
        attendance_pct = attendance_pct if shared["attendance"] else None
    return {
        "name": student["name"],
        "prn": student["prn"],
        "class": " · ".join(x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x),
        "academic_year": current["name"] if current else None,
        "photo_url": f"/files/{student['photo_file_id']}" if student.get("photo_file_id") else None,
        "balance": balance,
        "attendance": attendance_pct,
        "cards": cards,
    }
