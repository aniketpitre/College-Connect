"""
Grievance redressal (spec §3.15, plan 3.9).

A student raises a grievance in a category, optionally anonymously: then no staff member sees
who raised it (the audit log doesn't name them either). Each category has a time limit in
working days; a grievance not resolved by then is escalated by the daily job and the Principal
is emailed (the Internal Complaints Committee for sensitive cases). Sensitive categories
(ragging, harassment) are seen only by ICC members, never by the Grievance Cell or the
Principal, who see only counts.

open → in progress (a handler takes it) → resolved (with the resolution, the student is told)
→ closed (the student is satisfied, or says nothing for a week). A dissatisfied student can
reopen it once; a reopened grievance goes straight to the Principal (or the ICC).
"""

from datetime import timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.certificates.service import add_working_days
from app.modules.grievance.schemas import ActionIn, FeedbackIn, GrievanceIn, SlaSettings
from app.modules.messaging import service as messaging
from app.modules.students import service as students

register_indexes(
    "grievances",
    [
        IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("sensitive", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)]),
    ],
)

SETTINGS_ID = "grievance"
CATEGORIES = {
    "academic": "Academic",
    "examination": "Examination",
    "fees": "Fees and scholarships",
    "infrastructure": "Infrastructure",
    "library": "Library",
    "hostel": "Hostel",
    "ragging": "Ragging",
    "harassment": "Harassment",
    "other": "Other",
}
SENSITIVE = frozenset({"ragging", "harassment"})
DEFAULT_SLA = {
    "academic": 7,
    "examination": 7,
    "fees": 5,
    "infrastructure": 10,
    "library": 5,
    "hostel": 5,
    "ragging": 3,
    "harassment": 10,
    "other": 7,
}
OPEN = ("open", "in_progress")
STATUS_LABELS = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved", "closed": "Closed"}


def settings() -> dict[str, Any]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID}) or {}
    return {"sla_days": {**DEFAULT_SLA, **doc.get("sla_days", {})}, "close_after_days": doc.get("close_after_days", 7)}


def save_settings(ctx: AuthContext, body: SlaSettings) -> dict[str, Any]:
    if any(not 1 <= d <= 90 for d in body.sla_days.values()):
        raise AppError(422, "Each time limit must be 1 to 90 working days.", field="sla_days")
    data = body.model_dump()
    get_db().settings.update_one({"_id": SETTINGS_ID}, {"$set": data}, upsert=True)
    audit.record("grievance.settings_updated", actor_id=ctx.user_id, details=data)
    return settings()


# --- who sees what --------------------------------------------------------------------------


def scope(ctx: AuthContext) -> dict[str, Any]:
    """The grievances this staff member may read."""
    perms = ctx.permissions
    allowed = []
    if P.GRIEVANCE_MANAGE in perms or P.GRIEVANCE_READ in perms:
        allowed.append({"sensitive": False})
    if P.GRIEVANCE_SENSITIVE in perms:
        allowed.append({"sensitive": True})
    if not allowed:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return {"$or": allowed}


def _can_act(ctx: AuthContext, g: dict[str, Any]) -> bool:
    return (P.GRIEVANCE_SENSITIVE if g["sensitive"] else P.GRIEVANCE_MANAGE) in ctx.permissions


def _get(ctx: AuthContext, grievance_id: str) -> dict[str, Any]:
    g = get_db().grievances.find_one({"_id": students.oid(grievance_id, "Grievance"), **scope(ctx)})
    if not g:
        raise AppError(404, "Grievance not found.")
    return g


# --- views ----------------------------------------------------------------------------------


def _overdue(g: dict[str, Any]) -> bool:
    return g["status"] in OPEN and g["due_date"] < clock.today().isoformat()


def _event(kind: str, by: str, ctx: AuthContext | None = None, text: str | None = None) -> dict[str, Any]:
    return {
        "at": clock.now(),
        "kind": kind,
        "by": by,
        "user_id": ctx.user_id if ctx and by == "staff" else None,
        "name": ctx.user.get("name") if ctx and by == "staff" else None,
        "text": text,
    }


def _base(g: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(g["_id"]),
        "number": g["number"],
        "category": g["category"],
        "category_label": CATEGORIES[g["category"]],
        "subject": g["subject"],
        "text": g["text"],
        "status": g["status"],
        "status_label": STATUS_LABELS[g["status"]],
        "anonymous": g["anonymous"],
        "sensitive": g["sensitive"],
        "created_at": g["created_at"],
        "due_date": g["due_date"],
        "overdue": _overdue(g),
        "escalated": bool(g.get("escalated_at")),
        "resolution": g.get("resolution"),
        "resolved_at": g.get("resolved_at"),
        "feedback": g.get("feedback"),
        "reopened": g.get("reopened", 0),
    }


def staff_view(g: dict[str, Any], *, full: bool = False) -> dict[str, Any]:
    out = _base(g)
    student = None
    if not g["anonymous"]:
        s = get_db().students.find_one({"_id": g["student_id"]}, {"name": 1, "prn": 1})
        student = {"name": s["name"], "prn": s.get("prn")} if s else None
    out["student"] = student
    out["handler"] = g.get("handler_name")
    if full:
        out["history"] = [{k: v for k, v in h.items() if k != "user_id"} for h in g.get("history", [])]
    return out


def student_view(g: dict[str, Any]) -> dict[str, Any]:
    out = _base(g)
    out["history"] = [
        {"at": h["at"], "kind": h["kind"], "by": h["by"], "text": h.get("text")}
        for h in g.get("history", [])
        if h["kind"] != "note"  # internal notes stay with staff
    ]
    return out


# --- students -------------------------------------------------------------------------------


def _mine(ctx: AuthContext, grievance_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    student = students.my_student(ctx)
    g = get_db().grievances.find_one({"_id": students.oid(grievance_id, "Grievance"), "student_id": student["_id"]})
    if not g:
        raise AppError(404, "Grievance not found.")
    return student, g


def _audit_actor(ctx: AuthContext, g: dict[str, Any]) -> ObjectId | None:
    """Anonymous grievances don't name the student even in the audit log."""
    return None if g["anonymous"] else ctx.user_id


def raise_grievance(ctx: AuthContext, body: GrievanceIn) -> dict[str, Any]:
    student = students.my_student(ctx)
    db = get_db()
    today = clock.today()
    if (
        db.grievances.count_documents(
            {"student_id": student["_id"], "created_at": {"$gte": clock.now() - timedelta(days=1)}}
        )
        >= 5
    ):
        raise AppError(429, "You have raised 5 grievances today. Please wait until tomorrow.", "too_many")
    counter = db.counters.find_one_and_update(
        {"_id": f"grievance:{today.year}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    assert counter is not None
    g = {
        "number": f"GRV/{today.year}/{counter['seq']:05d}",
        "student_id": student["_id"],
        "category": body.category,
        "subject": body.subject.strip(),
        "text": body.text.strip(),
        "anonymous": body.anonymous,
        "sensitive": body.category in SENSITIVE,
        "status": "open",
        "created_at": clock.now(),
        "due_date": add_working_days(today, settings()["sla_days"][body.category]).isoformat(),
        "history": [_event("raised", "student")],
        "reopened": 0,
    }
    g["_id"] = db.grievances.insert_one(g).inserted_id
    audit.record(
        "grievance.raised",
        actor_id=_audit_actor(ctx, g),
        target_type="grievance",
        target_id=g["_id"],
        details={"number": g["number"], "category": g["category"]},
    )
    return student_view(g)


def my_grievances(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    rows = get_db().grievances.find({"student_id": student["_id"]}).sort("created_at", DESCENDING).limit(100)
    return {
        "grievances": [student_view(g) for g in rows],
        "categories": [{"key": k, "label": v, "sensitive": k in SENSITIVE} for k, v in CATEGORIES.items()],
        "sla_days": settings()["sla_days"],
    }


def my_grievance(ctx: AuthContext, grievance_id: str) -> dict[str, Any]:
    return student_view(_mine(ctx, grievance_id)[1])


def comment(ctx: AuthContext, grievance_id: str, text: str) -> dict[str, Any]:
    _, g = _mine(ctx, grievance_id)
    if g["status"] not in OPEN:
        raise AppError(409, "This grievance is no longer open.", "conflict")
    return student_view(_push(g, _event("comment", "student", text=text.strip())))


def feedback(ctx: AuthContext, grievance_id: str, body: FeedbackIn) -> dict[str, Any]:
    _, g = _mine(ctx, grievance_id)
    if g["status"] != "resolved":
        raise AppError(409, "You can give feedback once the grievance is resolved.", "conflict")
    note = (body.comment or "").strip() or None
    fb = {"satisfied": body.satisfied, "rating": body.rating, "comment": note}
    db = get_db()
    if body.satisfied or g.get("reopened", 0) >= 1:
        changes: dict[str, Any] = {"status": "closed", "closed_at": clock.now(), "feedback": fb}
        events = [_event("feedback", "student", text=note), _event("closed", "student")]
    else:
        due = add_working_days(clock.today(), 3).isoformat()
        changes = {"status": "open", "feedback": fb, "reopened": 1, "due_date": due, "escalated_at": clock.now()}
        events = [_event("reopened", "student", text=note)]
    db.grievances.update_one({"_id": g["_id"]}, {"$set": changes, "$push": {"history": {"$each": events}}})
    g = db.grievances.find_one({"_id": g["_id"]}) or g
    if changes["status"] == "open":
        _email_escalation([g], "reopened by the student")
    audit.record(
        "grievance.feedback",
        actor_id=_audit_actor(ctx, g),
        target_type="grievance",
        target_id=g["_id"],
        details={"number": g["number"], "satisfied": body.satisfied, "rating": body.rating},
    )
    return student_view(g)


def _push(g: dict[str, Any], event: dict[str, Any], changes: dict[str, Any] | None = None) -> dict[str, Any]:
    db = get_db()
    update: dict[str, Any] = {"$push": {"history": event}}
    if changes:
        update["$set"] = changes
    return db.grievances.find_one_and_update({"_id": g["_id"]}, update, return_document=ReturnDocument.AFTER) or g


# --- staff ----------------------------------------------------------------------------------


def listing(ctx: AuthContext, status: str, category: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = dict(scope(ctx))
    today = clock.today().isoformat()
    if status == "open":
        query["status"] = {"$in": list(OPEN)}
    elif status == "overdue":
        query["status"] = {"$in": list(OPEN)}
        query["due_date"] = {"$lt": today}
    else:
        query["status"] = status
    if category:
        query["category"] = category
    order = [("due_date", ASCENDING)] if status in {"open", "overdue"} else [("created_at", DESCENDING)]
    return [staff_view(g) for g in get_db().grievances.find(query).sort(order).limit(300)]


def detail(ctx: AuthContext, grievance_id: str) -> dict[str, Any]:
    g = _get(ctx, grievance_id)
    return {**staff_view(g, full=True), "can_act": _can_act(ctx, g)}


def act(ctx: AuthContext, grievance_id: str, body: ActionIn, ip: str) -> dict[str, Any]:
    g = _get(ctx, grievance_id)
    if not _can_act(ctx, g):
        raise AppError(403, "You can read this grievance but not act on it.", "forbidden")
    text = (body.text or "").strip() or None
    if g["status"] not in OPEN:
        raise AppError(409, "This grievance is no longer open.", "conflict")
    if body.action in {"reply", "note", "resolve"} and not text:
        raise AppError(422, "Write a few words first.", field="text")
    changes: dict[str, Any] = {}
    if body.action == "take":
        changes = {"status": "in_progress", "handler_id": ctx.user_id, "handler_name": ctx.user.get("name")}
    elif body.action == "resolve":
        changes = {"status": "resolved", "resolution": text, "resolved_at": clock.now()}
    elif g["status"] == "open":  # a reply or note means someone is on it
        changes = {"status": "in_progress", "handler_id": ctx.user_id, "handler_name": ctx.user.get("name")}
    kind = {"take": "taken", "resolve": "resolved"}.get(body.action, body.action)
    g = _push(g, _event(kind, "staff", ctx, text), changes)
    if body.action in {"reply", "resolve"}:
        student = get_db().students.find_one({"_id": g["student_id"]})
        if student:
            key = "grievance_resolved" if body.action == "resolve" else "grievance_replied"
            messaging.notify(student, key, {"number": g["number"]})
    audit.record(
        f"grievance.{kind}",
        actor_id=ctx.user_id,
        target_type="grievance",
        target_id=g["_id"],
        ip=ip,
        details={"number": g["number"]},
    )
    return {**staff_view(g, full=True), "can_act": True}


def stats(ctx: AuthContext) -> dict[str, Any]:
    """Counts for the cell and the Principal (NAAC: grievances received and redressed)."""
    perms = ctx.permissions
    if not perms & {P.GRIEVANCE_READ, P.GRIEVANCE_MANAGE, P.GRIEVANCE_SENSITIVE}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    db = get_db()
    today = clock.today().isoformat()
    rows = list(
        db.grievances.find(
            {}, {"category": 1, "status": 1, "due_date": 1, "created_at": 1, "resolved_at": 1, "feedback": 1}
        )
    )
    by_category = []
    for key, label in CATEGORIES.items():
        mine = [g for g in rows if g["category"] == key]
        by_category.append(
            {
                "category": key,
                "label": label,
                "received": len(mine),
                "open": sum(1 for g in mine if g["status"] in OPEN),
                "resolved": sum(1 for g in mine if g["status"] in {"resolved", "closed"}),
            }
        )
    done = [g for g in rows if g.get("resolved_at")]
    in_time = sum(1 for g in done if g["resolved_at"].astimezone(clock.IST).date().isoformat() <= g["due_date"])
    days = [(g["resolved_at"] - g["created_at"]).total_seconds() / 86400 for g in done]
    feedbacks = [g["feedback"] for g in rows if g.get("feedback")]
    return {
        "received": len(rows),
        "open": sum(1 for g in rows if g["status"] in OPEN),
        "overdue": sum(1 for g in rows if g["status"] in OPEN and g["due_date"] < today),
        "resolved": len(done),
        "resolved_in_time": in_time,
        "average_days": round(sum(days) / len(days), 1) if days else None,
        "satisfied": sum(1 for f in feedbacks if f["satisfied"]),
        "feedback": len(feedbacks),
        "average_rating": round(sum(f["rating"] for f in feedbacks) / len(feedbacks), 1) if feedbacks else None,
        "by_category": by_category,
    }


# --- daily job ------------------------------------------------------------------------------


def _email_escalation(rows: list[dict[str, Any]], why: str) -> int:
    """Emails the Principal(s) about ordinary grievances and ICC members about sensitive ones,
    without naming the students."""
    db = get_db()
    sent = 0
    for sensitive, role in ((False, "principal"), (True, "icc")):
        mine = [g for g in rows if g["sensitive"] is sensitive]
        if not mine:
            continue
        lines = [f"- {g['number']} · {CATEGORIES[g['category']]} · due {g['due_date']}" for g in mine]
        for u in db.users.find({"roles": role, "status": "active", "email": {"$ne": None}}, {"email": 1}):
            if send_email(
                u["email"],
                f"{len(mine)} grievance(s) need your attention",
                f"These grievances were {why}:\n\n" + "\n".join(lines) + "\n\nOpen CollegeConnect → Grievances.\n",
            ):
                sent += 1
    return sent


def daily() -> dict[str, int]:
    db = get_db()
    today = clock.today().isoformat()
    late = list(db.grievances.find({"status": {"$in": list(OPEN)}, "due_date": {"$lt": today}, "escalated_at": None}))
    if late:
        db.grievances.update_many(
            {"_id": {"$in": [g["_id"] for g in late]}},
            {"$set": {"escalated_at": clock.now()}, "$push": {"history": _event("escalated", "system")}},
        )
    emailed = _email_escalation(late, "not resolved in time") if late else 0
    days = settings()["close_after_days"]
    stale = db.grievances.update_many(
        {"status": "resolved", "resolved_at": {"$lt": clock.now() - timedelta(days=days)}},
        {
            "$set": {"status": "closed", "closed_at": clock.now()},
            "$push": {"history": _event("closed", "system", text=f"No feedback within {days} days")},
        },
    )
    if late or stale.modified_count:
        audit.record("grievance.daily", details={"escalated": len(late), "closed": stale.modified_count})
    return {"escalated": len(late), "emailed": emailed, "closed": stale.modified_count}
