"""
Requests that change money and need the Principal's approval (spec R2, §3.4):
concessions, receipt cancellations and refunds.

The person who asks can never be the person who approves. On approval the change is posted to
the ledger in the same transaction that marks the request approved.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.modules.fees import ledger
from app.modules.fees.schemas import ConcessionIn
from app.modules.fees.service import find, oid
from app.modules.students import service as students

register_indexes(
    "approvals",
    [
        IndexModel([("status", ASCENDING), ("requested_at", ASCENDING)]),
        IndexModel([("student_id", ASCENDING), ("requested_at", DESCENDING)]),
        # Only one open request per receipt (e.g. two cancellation requests for the same receipt).
        IndexModel([("open_key", ASCENDING)], unique=True, partialFilterExpression={"open_key": {"$type": "string"}}),
    ],
)

KIND_LABELS = {"concession": "Concession", "receipt_cancel": "Cancel receipt", "refund": "Refund"}
CONCESSION_KINDS = {
    "staff_ward": "Staff ward",
    "sibling": "Sibling",
    "merit": "Merit",
    "sports": "Sports",
    "need_based": "Need-based",
    "other": "Other",
}

# kind → function(ctx, approval, session, ip) that applies an approved request. 1.10 adds more.
Handler = Callable[[AuthContext, dict[str, Any], ClientSession, str], dict[str, Any] | None]
HANDLERS: dict[str, Handler] = {}


def create(
    ctx: AuthContext,
    *,
    kind: str,
    student: dict[str, Any],
    academic_year_id: ObjectId,
    amount: int,
    reason: str,
    details: dict[str, Any],
    ip: str,
    open_key: str | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "kind": kind,
        "status": "pending",
        "student_id": student["_id"],
        "academic_year_id": academic_year_id,
        "amount": amount,
        "reason": reason.strip(),
        "details": details,
        "requested_by": ctx.user_id,
        "requested_at": datetime.now(UTC),
    }
    if open_key:
        doc["open_key"] = open_key
    try:
        doc["_id"] = get_db().approvals.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "A request for this is already waiting for approval.", "conflict") from e
    audit.record(
        f"fees.{kind}.requested",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        reason=reason,
        details={"approval_id": str(doc["_id"]), "amount": amount, **students.jsonable(details)},
    )
    return view(doc)


def request_concession(ctx: AuthContext, body: ConcessionIn, ip: str) -> dict[str, Any]:
    student = students.get_student(oid(body.student_id, "Student"))
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )
    head = find("fee_heads", oid(body.head_id, "Fee head", "head_id"), "Fee head", "head_id")
    owed = ledger.by_head(ledger.entries(student["_id"], year["_id"])).get(head["_id"], 0)
    if body.amount > owed:
        raise AppError(422, f"The student owes only {owed / 100:.2f} on {head['code']}.", field="amount")
    return create(
        ctx,
        kind="concession",
        student=student,
        academic_year_id=year["_id"],
        amount=body.amount,
        reason=body.reason,
        details={"head_id": head["_id"], "concession_kind": body.kind},
        ip=ip,
    )


def _apply_concession(ctx: AuthContext, approval: dict[str, Any], session: ClientSession, ip: str) -> dict[str, Any]:
    head_id = approval["details"]["head_id"]
    rows = ledger.entries(approval["student_id"], approval["academic_year_id"], session=session)
    owed = ledger.by_head(rows).get(head_id, 0)
    if approval["amount"] > owed:
        raise AppError(
            409, "The student now owes less on this fee head than the concession. Reject it and ask again.", "conflict"
        )
    return ledger.post(
        student_id=approval["student_id"],
        academic_year_id=approval["academic_year_id"],
        type="concession",
        lines=[{"head_id": head_id, "amount": -approval["amount"]}],
        created_by=ctx.user_id,
        session=session,
        ref={"type": "approval", "id": approval["_id"]},
        reason=approval["reason"],
    )


HANDLERS["concession"] = _apply_concession


def decide(ctx: AuthContext, approval_id: str, approve: bool, reason: str | None, ip: str) -> dict[str, Any]:
    aid = oid(approval_id, "Request")
    db = get_db()
    pending = db.approvals.find_one({"_id": aid})
    if not pending:
        raise AppError(404, "Request not found.")
    if pending["requested_by"] == ctx.user_id:
        raise AppError(403, "You can't approve your own request.", "same_person")
    if not approve and not (reason and reason.strip()):
        raise AppError(422, "Give a reason for rejecting.", field="reason")

    def work(session: ClientSession) -> dict[str, Any]:
        approval = db.approvals.find_one_and_update(
            {"_id": aid, "status": "pending"},
            {
                "$set": {
                    "status": "approved" if approve else "rejected",
                    "decided_by": ctx.user_id,
                    "decided_at": datetime.now(UTC),
                    "decision_reason": (reason or "").strip() or None,
                },
                "$unset": {"open_key": ""},
            },
            session=session,
            return_document=True,
        )
        if not approval:
            raise AppError(409, "This request was already decided.", "conflict")
        if approve:
            entry = HANDLERS[approval["kind"]](ctx, approval, session, ip)
            if entry:
                db.approvals.update_one({"_id": aid}, {"$set": {"entry_id": entry["_id"]}}, session=session)
        audit.record(
            f"fees.{approval['kind']}.{'approved' if approve else 'rejected'}",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=approval["student_id"],
            ip=ip,
            reason=reason,
            details={"approval_id": str(aid), "amount": approval["amount"]},
            session=session,
        )
        return approval

    run_in_transaction(work)
    doc = db.approvals.find_one({"_id": aid})
    assert doc is not None
    return view(doc)


def view(a: dict[str, Any], names: dict[Any, str] | None = None, stud: dict[Any, dict] | None = None) -> dict[str, Any]:
    names = names or {}
    s = (stud or {}).get(a["student_id"], {})
    return {
        "id": str(a["_id"]),
        "kind": a["kind"],
        "kind_label": KIND_LABELS.get(a["kind"], a["kind"]),
        "status": a["status"],
        "student_id": str(a["student_id"]),
        "student_name": s.get("name"),
        "prn": s.get("prn"),
        "academic_year_id": str(a["academic_year_id"]),
        "amount": a["amount"],
        "reason": a["reason"],
        "details": students.jsonable(a.get("details", {})),
        "requested_by": names.get(a["requested_by"]),
        "requested_by_id": str(a["requested_by"]),
        "requested_at": a["requested_at"].isoformat(),
        "decided_by": names.get(a.get("decided_by")) if a.get("decided_by") else None,
        "decided_at": a["decided_at"].isoformat() if a.get("decided_at") else None,
        "decision_reason": a.get("decision_reason"),
    }


def list_requests(status: str | None, student_id: str | None, kind: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if kind:
        query["kind"] = kind
    if student_id:
        query["student_id"] = oid(student_id, "Student")
    db = get_db()
    rows = list(
        db.approvals.find(query).sort("requested_at", ASCENDING if status == "pending" else DESCENDING).limit(500)
    )
    people = {
        u["_id"]: u["name"]
        for u in db.users.find(
            {
                "_id": {
                    "$in": [r["requested_by"] for r in rows] + [r["decided_by"] for r in rows if r.get("decided_by")]
                }
            },
            {"name": 1},
        )
    }
    stud = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}}, {"name": 1, "prn": 1})
    }
    heads = {h["_id"]: h["code"] for h in db.fee_heads.find({}, {"code": 1})}
    result = []
    for r in rows:
        v = view(r, people, stud)
        if r["kind"] == "concession":
            v["details"]["head"] = heads.get(r["details"]["head_id"])
            v["details"]["concession_label"] = CONCESSION_KINDS.get(r["details"].get("concession_kind", ""), "")
        result.append(v)
    return result
