"""
Government scholarships (MahaDBT, NSP, …): expected → sanctioned → received (spec §3.4).

When a scholarship is sanctioned the student owes that much less (a scholarship credit in their
ledger); what the government still has to pay the college is `sanctioned - received`, shown in
the scholarship receivable report. A sanctioned scholarship that is later rejected is reversed.
"""

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.modules.fees import ledger
from app.modules.fees.schemas import ScholarshipAction, ScholarshipIn
from app.modules.fees.service import find, oid
from app.modules.students import service as students

register_indexes(
    "scholarships",
    [IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]), IndexModel([("status", ASCENDING)])],
)


def view(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(s["_id"]),
        "student_id": str(s["student_id"]),
        "academic_year_id": str(s["academic_year_id"]),
        "scheme": s["scheme"],
        "reference": s.get("reference", ""),
        "expected": s["expected"],
        "sanctioned": s.get("sanctioned", 0),
        "received": s.get("received", 0),
        "status": s["status"],
        "history": students.jsonable(s.get("history", [])),
    }


def list_for(student_id: str | None, academic_year_id: str | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if student_id:
        query["student_id"] = oid(student_id, "Student")
    if academic_year_id:
        query["academic_year_id"] = oid(academic_year_id, "Academic year")
    return [view(s) for s in get_db().scholarships.find(query).sort("created_at", DESCENDING)]


def create(ctx: AuthContext, body: ScholarshipIn, ip: str) -> dict[str, Any]:
    student = students.get_student(oid(body.student_id, "Student"))
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )
    now = datetime.now(UTC)
    doc = {
        "student_id": student["_id"],
        "academic_year_id": year["_id"],
        "scheme": body.scheme.strip(),
        "reference": body.reference.strip(),
        "expected": body.expected,
        "sanctioned": 0,
        "received": 0,
        "status": "expected",
        "history": [{"at": now, "by": ctx.user_id, "action": "expected", "amount": body.expected}],
        "created_at": now,
        "created_by": ctx.user_id,
    }
    doc["_id"] = get_db().scholarships.insert_one(doc).inserted_id
    audit.record(
        "fees.scholarship.recorded",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"scheme": doc["scheme"], "expected": body.expected},
    )
    return view(doc)


def act(ctx: AuthContext, scholarship_id: str, body: ScholarshipAction, ip: str) -> dict[str, Any]:
    sid = oid(scholarship_id, "Scholarship")
    db = get_db()

    def work(session: ClientSession) -> None:
        s = db.scholarships.find_one({"_id": sid}, session=session)
        if not s:
            raise AppError(404, "Scholarship not found.")
        now = datetime.now(UTC)
        changes: dict[str, Any] = {}
        if body.action == "sanction":
            if s["status"] != "expected":
                raise AppError(409, "Only an expected scholarship can be sanctioned.", "conflict")
            amount = body.amount or s["expected"]
            rows = ledger.entries(s["student_id"], s["academic_year_id"], session=session)
            balance = sum(e["amount"] for e in rows)
            if amount > balance:
                raise AppError(
                    422,
                    f"The student owes only {balance / 100:.2f}; record the rest as a refund later.",
                    field="amount",
                )
            entry = ledger.post(
                student_id=s["student_id"],
                academic_year_id=s["academic_year_id"],
                type="scholarship",
                lines=ledger.allocate(amount, ledger.by_head(rows), ledger.head_order(rows)),
                created_by=ctx.user_id,
                session=session,
                ref={"type": "scholarship", "id": sid},
                reason=f"{s['scheme']} sanctioned",
            )
            changes = {"status": "sanctioned", "sanctioned": amount, "entry_id": entry["_id"]}
        elif body.action == "receive":
            if s["status"] not in {"sanctioned", "received"}:
                raise AppError(409, "Record the sanction first.", "conflict")
            amount = body.amount or (s["sanctioned"] - s["received"])
            received = s["received"] + amount
            if received > s["sanctioned"]:
                raise AppError(422, "More than the sanctioned amount.", field="amount")
            changes = {"received": received, "status": "received" if received == s["sanctioned"] else "sanctioned"}
        else:  # reject
            if s["status"] == "rejected" or s.get("received"):
                raise AppError(409, "This scholarship can't be rejected now.", "conflict")
            if not body.reason:
                raise AppError(422, "Give a reason.", field="reason")
            if s["status"] == "sanctioned":
                credit = db.ledger_entries.find_one({"_id": s["entry_id"]}, session=session)
                assert credit is not None
                ledger.post(
                    student_id=s["student_id"],
                    academic_year_id=s["academic_year_id"],
                    type="reversal",
                    lines=[{"head_id": ln["head_id"], "amount": -ln["amount"]} for ln in credit["lines"]],
                    created_by=ctx.user_id,
                    session=session,
                    ref={"type": "scholarship", "id": sid},
                    reason=f"{s['scheme']} rejected: {body.reason}",
                    reverses=credit["_id"],
                )
                db.ledger_entries.update_one({"_id": credit["_id"]}, {"$set": {"reversed": True}}, session=session)
            changes = {"status": "rejected"}
        if body.reference:
            changes["reference"] = body.reference
        db.scholarships.update_one(
            {"_id": sid},
            {
                "$set": changes,
                "$push": {
                    "history": {
                        "at": now,
                        "by": ctx.user_id,
                        "action": body.action,
                        "amount": body.amount,
                        "reason": body.reason,
                    }
                },
            },
            session=session,
        )
        audit.record(
            f"fees.scholarship.{body.action}",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=s["student_id"],
            ip=ip,
            reason=body.reason,
            details={"scholarship_id": str(sid), "amount": body.amount},
            session=session,
        )

    run_in_transaction(work)
    doc = db.scholarships.find_one({"_id": sid})
    assert doc is not None
    return view(doc)
