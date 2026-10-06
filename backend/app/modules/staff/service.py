"""
Staff records and leave (spec §3.16, plan 3.10). Payroll is a later, separate project.

Staff records: the office keeps each staff member's designation, employment type,
qualifications (with NET/SET and Ph.D., which NAAC and AISHE count) and appointment details.

Leave: leave types with a yearly allowance are settings. A balance is computed, never stored:
the allowance plus any adjustments the office made (carried-forward leave, with a reason) minus
the days approved or waiting for approval in the current academic year. Days are working days
(Sundays and college holidays don't count). Faculty apply to their HOD; HODs, staff without a
department and non-teaching staff apply to the Principal; the Principal's own leave is recorded
as approved. The approver sees the lectures the person would miss, to arrange substitutes in the
timetable.
"""

from datetime import date, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.setup import service as setup
from app.modules.staff.schemas import AdjustIn, DecideIn, LeaveIn, LeaveSettings, StaffProfileIn
from app.modules.students import service as students
from app.modules.timetable import service as timetable

register_indexes(
    "staff_profiles",
    [
        IndexModel(
            [("employee_code", ASCENDING)], unique=True, partialFilterExpression={"employee_code": {"$type": "string"}}
        )
    ],
)
register_indexes(
    "leave_requests",
    [
        IndexModel([("user_id", ASCENDING), ("from_date", DESCENDING)]),
        IndexModel([("status", ASCENDING), ("approver", ASCENDING), ("department_id", ASCENDING)]),
    ],
)
register_indexes("leave_adjustments", [IndexModel([("user_id", ASCENDING), ("year_id", ASCENDING)])])

SETTINGS_ID = "leave"
DEFAULT_TYPES: list[dict[str, Any]] = [
    {"code": "CL", "name": "Casual leave", "days": 8, "half_day": True},
    {"code": "ML", "name": "Medical leave", "days": 10, "half_day": False},
    {"code": "EL", "name": "Earned leave", "days": 15, "half_day": False},
    {"code": "OD", "name": "On duty", "days": None, "half_day": True},
    {"code": "LWP", "name": "Leave without pay", "days": None, "half_day": True},
]
TEACHING = {"faculty", "hod", "mentor", "principal"}
ACTIVE = ("pending", "approved")
EMPLOYMENT = {"permanent": "Permanent", "contract": "Contract", "visiting": "Visiting", "ad_hoc": "Ad hoc"}


def oid(value: Any, what: str) -> ObjectId:
    return students.oid(value, what)


def _names(ids: list[ObjectId]) -> dict[ObjectId, str]:
    return {u["_id"]: u["name"] for u in get_db().users.find({"_id": {"$in": ids}}, {"name": 1})}


# --- staff records --------------------------------------------------------------------------


def _scope(ctx: AuthContext) -> dict[str, Any]:
    """The staff accounts this person may see: everyone, or their own department (HOD)."""
    if P.STAFF_READ in ctx.permissions:
        return {}
    if P.STAFF_READ_DEPT in ctx.permissions and ctx.user.get("department_id"):
        return {"department_id": ctx.user["department_id"]}
    raise AppError(403, "You don't have permission to do this.", "forbidden")


def _departments() -> dict[ObjectId, str]:
    return {d["_id"]: d["name"] for d in get_db().departments.find({}, {"name": 1})}


def _profile_view(u: dict[str, Any], p: dict[str, Any] | None, depts: dict[ObjectId, str]) -> dict[str, Any]:
    p = p or {}
    quals = p.get("qualifications", [])
    levels = {q["level"] for q in quals}
    return {
        "user_id": str(u["_id"]),
        "name": u["name"],
        "email": u.get("email"),
        "roles": u.get("roles", []),
        "status": u.get("status"),
        "department_id": str(u["department_id"]) if u.get("department_id") else None,
        "department": depts.get(u.get("department_id")),  # type: ignore[arg-type]
        "has_record": bool(p),
        "employee_code": p.get("employee_code"),
        "designation": p.get("designation"),
        "employment": p.get("employment"),
        "teaching": p.get("teaching", bool(set(u.get("roles", [])) & TEACHING)),
        "joined_on": p.get("joined_on"),
        "experience_years": p.get("experience_years", 0),
        "phone": p.get("phone"),
        "qualifications": quals,
        "phd": "phd" in levels,
        "net_set": bool(levels & {"net", "set"}),
        "appointment_order": p.get("appointment_order"),
        "appointment_date": p.get("appointment_date"),
        "university_approved": p.get("university_approved", False),
        "left_on": p.get("left_on"),
    }


def _staff_users(query: dict[str, Any]) -> list[dict[str, Any]]:
    return list(get_db().users.find({"kind": "staff", **query}, {"password_hash": 0}).sort("name", ASCENDING))


def staff_list(ctx: AuthContext) -> list[dict[str, Any]]:
    users = _staff_users({**_scope(ctx), "status": {"$ne": "disabled"}})
    profiles = {p["_id"]: p for p in get_db().staff_profiles.find({"_id": {"$in": [u["_id"] for u in users]}})}
    depts = _departments()
    return [_profile_view(u, profiles.get(u["_id"]), depts) for u in users]


def _staff_user(ctx: AuthContext | None, user_id: Any) -> dict[str, Any]:
    query: dict[str, Any] = {"_id": oid(user_id, "Staff member"), "kind": "staff"}
    if ctx is not None:
        query.update(_scope(ctx))
    u = get_db().users.find_one(query, {"password_hash": 0})
    if not u:
        raise AppError(404, "Staff member not found.")
    return u


def profile(ctx: AuthContext, user_id: str) -> dict[str, Any]:
    u = _staff_user(ctx, user_id)
    return _profile_view(u, get_db().staff_profiles.find_one({"_id": u["_id"]}), _departments())


def my_profile(ctx: AuthContext) -> dict[str, Any]:
    if ctx.user.get("kind") != "staff":
        raise AppError(403, "This is for staff accounts.", "forbidden")
    return _profile_view(ctx.user, get_db().staff_profiles.find_one({"_id": ctx.user_id}), _departments())


def save_profile(ctx: AuthContext, user_id: str, body: StaffProfileIn, ip: str) -> dict[str, Any]:
    u = _staff_user(None, user_id)
    data = body.model_dump(mode="json")
    data["employee_code"] = (data["employee_code"] or "").strip().upper() or None
    db = get_db()
    if data["employee_code"] and db.staff_profiles.find_one(
        {"employee_code": data["employee_code"], "_id": {"$ne": u["_id"]}}
    ):
        raise AppError(409, "Another staff member has this employee code.", "conflict", "employee_code")
    before = db.staff_profiles.find_one({"_id": u["_id"]}) or {}
    db.staff_profiles.update_one(
        {"_id": u["_id"]}, {"$set": {**data, "updated_at": clock.now(), "updated_by": ctx.user_id}}, upsert=True
    )
    changed = sorted(k for k in data if before.get(k) != data[k])
    audit.record(
        "staff.profile_saved",
        actor_id=ctx.user_id,
        target_type="user",
        target_id=u["_id"],
        ip=ip,
        details={"fields": changed},
    )
    return _profile_view(u, db.staff_profiles.find_one({"_id": u["_id"]}), _departments())


def summary(ctx: AuthContext) -> dict[str, Any]:
    """Head counts for NAAC/AISHE: teaching and non-teaching, Ph.D., NET/SET, by department."""
    rows = staff_list(ctx)
    teaching = [r for r in rows if r["teaching"]]
    by_dept: dict[str, dict[str, Any]] = {}
    for r in teaching:
        d = by_dept.setdefault(r["department"] or "—", {"department": r["department"] or "—", "teachers": 0, "phd": 0})
        d["teachers"] += 1
        d["phd"] += int(r["phd"])
    return {
        "staff": len(rows),
        "teaching": len(teaching),
        "non_teaching": len(rows) - len(teaching),
        "phd": sum(1 for r in teaching if r["phd"]),
        "net_set": sum(1 for r in teaching if r["net_set"]),
        "by_employment": {k: sum(1 for r in teaching if r["employment"] == k) for k in EMPLOYMENT},
        "missing_records": sum(1 for r in rows if not r["has_record"]),
        "by_department": sorted(by_dept.values(), key=lambda d: d["department"]),
    }


# --- leave settings and balances -----------------------------------------------------------


def leave_types() -> list[dict[str, Any]]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID}) or {}
    types: list[dict[str, Any]] = doc.get("types") or [dict(t) for t in DEFAULT_TYPES]
    return types


def save_leave_settings(ctx: AuthContext, body: LeaveSettings) -> list[dict[str, Any]]:
    types = [t.model_dump() for t in body.types]
    get_db().settings.update_one({"_id": SETTINGS_ID}, {"$set": {"types": types}}, upsert=True)
    audit.record("leave.settings_updated", actor_id=ctx.user_id, details={"types": [t["code"] for t in types]})
    return leave_types()


def _year() -> dict[str, Any]:
    year = setup.current_year()
    if not year:
        raise AppError(409, "Set the current academic year in College setup first.", "no_current_year")
    return year


def working_days(first: date, last: date) -> list[date]:
    holidays = timetable.holidays_between(first, last)
    out, d = [], first
    while d <= last:
        if d.isoweekday() != 7 and d.isoformat() not in holidays:
            out.append(d)
        d += timedelta(days=1)
    return out


def balances(user_id: ObjectId, year: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    year = year or _year()
    db = get_db()
    in_year = {"user_id": user_id, "from_date": {"$gte": year["start_date"], "$lte": year["end_date"]}}
    used: dict[str, dict[str, float]] = {}
    for r in db.leave_requests.find({**in_year, "status": {"$in": list(ACTIVE)}}, {"code": 1, "days": 1, "status": 1}):
        used.setdefault(r["code"], {"approved": 0, "pending": 0})[r["status"]] += r["days"]
    adjusted: dict[str, float] = {}
    for a in db.leave_adjustments.find({"user_id": user_id, "year_id": year["_id"]}):
        adjusted[a["code"]] = adjusted.get(a["code"], 0) + a["days"]
    out = []
    for t in leave_types():
        u = used.get(t["code"], {"approved": 0, "pending": 0})
        allowance = None if t["days"] is None else t["days"] + adjusted.get(t["code"], 0)
        out.append(
            {
                "code": t["code"],
                "name": t["name"],
                "half_day": t["half_day"],
                "allowance": allowance,
                "taken": u["approved"],
                "pending": u["pending"],
                "available": None if allowance is None else allowance - u["approved"] - u["pending"],
            }
        )
    return out


def adjust(ctx: AuthContext, body: AdjustIn, ip: str) -> list[dict[str, Any]]:
    u = _staff_user(None, body.user_id)
    if body.code not in {t["code"] for t in leave_types()}:
        raise AppError(422, "Unknown leave type.", field="code")
    year = _year()
    get_db().leave_adjustments.insert_one(
        {
            "user_id": u["_id"],
            "year_id": year["_id"],
            "code": body.code,
            "days": body.days,
            "reason": body.reason.strip(),
            "by": ctx.user_id,
            "at": clock.now(),
        }
    )
    audit.record(
        "leave.adjusted",
        actor_id=ctx.user_id,
        target_type="user",
        target_id=u["_id"],
        ip=ip,
        reason=body.reason,
        details={"code": body.code, "days": body.days},
    )
    return balances(u["_id"], year)


# --- applying -------------------------------------------------------------------------------


def _approver(user: dict[str, Any]) -> str:
    roles = set(user.get("roles", []))
    if "principal" in roles:
        return "self"
    if "hod" in roles or not user.get("department_id") or not roles & TEACHING:
        return "principal"
    return "hod"


def _lectures(user_id: ObjectId, first: date, last: date) -> list[dict[str, Any]]:
    """Lectures this person would miss (for the approver to arrange substitutes)."""
    out = []
    for d in working_days(first, min(last, first + timedelta(days=31))):
        for lec in timetable.lectures_on(d, faculty_id=user_id, include_cancelled=False):
            if lec["status"] == "handed_over":
                continue
            out.append(
                {
                    "date": lec["date"],
                    "start": lec["start"],
                    "end": lec["end"],
                    "subject": lec.get("subject_code"),
                    "division": lec.get("division"),
                    "slot_id": lec["slot_id"],
                }
            )
    return out


def _view(r: dict[str, Any], *, names: dict[ObjectId, str] | None = None) -> dict[str, Any]:
    names = names or {}
    return {
        "id": str(r["_id"]),
        "user_id": str(r["user_id"]),
        "name": names.get(r["user_id"]),
        "code": r["code"],
        "type_name": r["type_name"],
        "from_date": r["from_date"],
        "to_date": r["to_date"],
        "half_day": r.get("half_day", False),
        "days": r["days"],
        "reason": r["reason"],
        "status": r["status"],
        "approver": r["approver"],
        "decided_by": names.get(r["decided_by"]) if r.get("decided_by") else None,
        "decided_at": r.get("decided_at"),
        "note": r.get("note"),
        "applied_at": r["applied_at"],
    }


def apply(ctx: AuthContext, body: LeaveIn, ip: str) -> dict[str, Any]:
    if ctx.user.get("kind") != "staff":
        raise AppError(403, "This is for staff accounts.", "forbidden")
    t = next((x for x in leave_types() if x["code"] == body.code), None)
    if not t:
        raise AppError(422, "Unknown leave type.", field="code")
    if body.half_day and not t["half_day"]:
        raise AppError(422, f"{t['name']} can't be taken for half a day.", field="half_day")
    year = _year()
    first, last = body.from_date.isoformat(), body.to_date.isoformat()
    if first < year["start_date"] or last > year["end_date"]:
        raise AppError(422, f"Apply within the academic year {year['name']}.", field="from_date")
    if body.from_date < clock.today() - timedelta(days=7):
        raise AppError(422, "Leave can be applied for at most a week after it was taken.", field="from_date")
    days = len(working_days(body.from_date, body.to_date))
    if days == 0:
        raise AppError(422, "These dates are all Sundays or holidays.", field="from_date")
    total = 0.5 if body.half_day else float(days)
    db = get_db()
    if db.leave_requests.find_one(
        {
            "user_id": ctx.user_id,
            "status": {"$in": list(ACTIVE)},
            "from_date": {"$lte": last},
            "to_date": {"$gte": first},
        }
    ):
        raise AppError(409, "You already have leave on some of these days.", "conflict", "from_date")
    balance = next(b for b in balances(ctx.user_id, year) if b["code"] == body.code)
    if balance["available"] is not None and total > balance["available"]:
        raise AppError(
            422,
            f"Only {balance['available']:g} day(s) of {t['name'].lower()} are left this year.",
            "no_balance",
            "code",
        )
    approver = _approver(ctx.user)
    r: dict[str, Any] = {
        "user_id": ctx.user_id,
        "department_id": ctx.user.get("department_id"),
        "code": body.code,
        "type_name": t["name"],
        "from_date": first,
        "to_date": last,
        "half_day": body.half_day,
        "days": total,
        "reason": body.reason.strip(),
        "status": "pending",
        "approver": approver,
        "applied_at": clock.now(),
    }
    if approver == "self":
        r.update(status="approved", decided_by=ctx.user_id, decided_at=clock.now(), note="Recorded by the Principal")
    r["_id"] = db.leave_requests.insert_one(r).inserted_id
    audit.record(
        "leave.applied",
        actor_id=ctx.user_id,
        target_type="leave",
        target_id=r["_id"],
        ip=ip,
        details={"code": body.code, "from": first, "to": last, "days": total},
    )
    if r["status"] == "pending":
        _tell_approvers(r, ctx.user)
    return _view(r, names={ctx.user_id: ctx.user["name"]})


def _approvers(r: dict[str, Any]) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"kind": "staff", "status": "active"}
    if r["approver"] == "hod":
        query.update(roles="hod", department_id=r["department_id"])
    else:
        query["roles"] = "principal"
    return list(get_db().users.find(query, {"email": 1, "name": 1}))


def _tell_approvers(r: dict[str, Any], applicant: dict[str, Any]) -> None:
    span = r["from_date"] if r["from_date"] == r["to_date"] else f"{r['from_date']} to {r['to_date']}"
    for a in _approvers(r):
        if a.get("email") and a["_id"] != applicant["_id"]:
            send_email(
                a["email"],
                f"Leave request: {applicant['name']}",
                f"{applicant['name']} has applied for {r['type_name'].lower()} ({r['days']:g} day(s), {span}).\n"
                f"Reason: {r['reason']}\n\nOpen CollegeConnect → Leave to approve or reject it.\n",
            )


def my_leave(ctx: AuthContext) -> dict[str, Any]:
    if ctx.user.get("kind") != "staff":
        raise AppError(403, "This is for staff accounts.", "forbidden")
    year = _year()
    rows = list(get_db().leave_requests.find({"user_id": ctx.user_id}).sort("from_date", DESCENDING).limit(100))
    users = {ctx.user_id: ctx.user["name"]}
    users.update(_names([r["decided_by"] for r in rows if r.get("decided_by")]))
    return {
        "year": year["name"],
        "balances": balances(ctx.user_id, year),
        "requests": [_view(r, names=users) for r in rows],
        "approver": _approver(ctx.user),
        "can_approve": P.LEAVE_APPROVE in ctx.permissions,
    }


def cancel(ctx: AuthContext, request_id: str, ip: str) -> dict[str, Any]:
    db = get_db()
    r = db.leave_requests.find_one({"_id": oid(request_id, "Leave request"), "user_id": ctx.user_id})
    if not r:
        raise AppError(404, "Leave request not found.")
    if r["status"] == "pending" or (r["status"] == "approved" and r["from_date"] > clock.today().isoformat()):
        db.leave_requests.update_one({"_id": r["_id"]}, {"$set": {"status": "cancelled", "cancelled_at": clock.now()}})
        audit.record("leave.cancelled", actor_id=ctx.user_id, target_type="leave", target_id=r["_id"], ip=ip)
        return my_leave(ctx)
    raise AppError(409, "Only pending leave, or approved leave that hasn't started, can be cancelled.", "conflict")


# --- approving ------------------------------------------------------------------------------


def approver_query(ctx: AuthContext) -> dict[str, Any]:
    if P.LEAVE_APPROVE not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    roles = set(ctx.user.get("roles", []))
    mine: list[dict[str, Any]] = []
    if "principal" in roles:
        mine.append({"approver": "principal"})
    if "hod" in roles and ctx.user.get("department_id"):
        mine.append({"approver": "hod", "department_id": ctx.user["department_id"]})
    if not mine:
        raise AppError(403, "You don't approve anyone's leave.", "forbidden")
    return {"$or": mine, "user_id": {"$ne": ctx.user_id}}


def requests_to_decide(ctx: AuthContext, status: str) -> list[dict[str, Any]]:
    db = get_db()
    query = approver_query(ctx)
    query["status"] = status
    rows = list(
        db.leave_requests.find(query).sort("from_date", ASCENDING if status == "pending" else DESCENDING).limit(200)
    )
    names = _names(list({r["user_id"] for r in rows} | {r["decided_by"] for r in rows if r.get("decided_by")}))
    out = []
    for r in rows:
        v = _view(r, names=names)
        if status == "pending":
            v["balance"] = next((b for b in balances(r["user_id"]) if b["code"] == r["code"]), None)
            v["lectures"] = _lectures(
                r["user_id"], date.fromisoformat(r["from_date"]), date.fromisoformat(r["to_date"])
            )
        out.append(v)
    return out


def decide(ctx: AuthContext, request_id: str, body: DecideIn, ip: str) -> dict[str, Any]:
    db = get_db()
    query = approver_query(ctx)
    r = db.leave_requests.find_one({"_id": oid(request_id, "Leave request"), **query})
    if not r:
        raise AppError(404, "Leave request not found.")
    if r["status"] != "pending":
        raise AppError(409, "This request has already been decided.", "conflict")
    if not body.approve and not (body.note and body.note.strip()):
        raise AppError(422, "Give a reason for rejecting.", field="note")
    status = "approved" if body.approve else "rejected"
    note = (body.note or "").strip() or None
    changes: dict[str, Any] = {
        "status": status,
        "decided_by": ctx.user_id,
        "decided_at": clock.now(),
        "note": note,
    }
    db.leave_requests.update_one({"_id": r["_id"], "status": "pending"}, {"$set": changes})
    r.update(changes)
    audit.record(
        f"leave.{status}",
        actor_id=ctx.user_id,
        target_type="leave",
        target_id=r["_id"],
        ip=ip,
        reason=note,
        details={"code": r["code"], "from": r["from_date"], "to": r["to_date"], "days": r["days"]},
    )
    person = db.users.find_one({"_id": r["user_id"]}, {"email": 1, "name": 1}) or {}
    if person.get("email"):
        span = r["from_date"] if r["from_date"] == r["to_date"] else f"{r['from_date']} to {r['to_date']}"
        send_email(
            person["email"],
            f"Leave {status}: {r['type_name']} {span}",
            f"Your {r['type_name'].lower()} ({r['days']:g} day(s), {span}) was {status} by {ctx.user['name']}."
            + (f"\nNote: {changes['note']}" if changes["note"] else "")
            + "\n",
        )
    return _view(r, names={r["user_id"]: person.get("name", ""), ctx.user_id: ctx.user["name"]})


# --- workload -------------------------------------------------------------------------------


def _minutes(start: str, end: str) -> int:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)


def workload(ctx: AuthContext) -> dict[str, Any]:
    """Teaching load per week from the timetable in force today, leave taken this year, and who
    is on leave today."""
    db = get_db()
    today = clock.today().isoformat()
    rows = [r for r in staff_list(ctx) if r["teaching"]]
    ids = [ObjectId(r["user_id"]) for r in rows]
    slots = list(
        db.timetable_slots.find(
            {
                "status": "active",
                "faculty_ids": {"$in": ids},
                "valid_from": {"$lte": today},
                "valid_to": {"$gte": today},
            },
            {"faculty_ids": 1, "start": 1, "end": 1, "subject_id": 1, "division_id": 1},
        )
    )
    year = setup.current_year()
    taken: dict[ObjectId, float] = {}
    away: set[ObjectId] = set()
    if year:
        for r in db.leave_requests.find(
            {
                "user_id": {"$in": ids},
                "status": "approved",
                "from_date": {"$gte": year["start_date"], "$lte": year["end_date"]},
            },
            {"user_id": 1, "days": 1, "from_date": 1, "to_date": 1},
        ):
            taken[r["user_id"]] = taken.get(r["user_id"], 0) + r["days"]
            if r["from_date"] <= today <= r["to_date"]:
                away.add(r["user_id"])
    out = []
    for r in rows:
        uid = ObjectId(r["user_id"])
        mine = [s for s in slots if uid in s["faculty_ids"]]
        out.append(
            {
                "user_id": r["user_id"],
                "name": r["name"],
                "department": r["department"],
                "designation": r["designation"],
                "lectures": len(mine),
                "hours": round(sum(_minutes(s["start"], s["end"]) for s in mine) / 60, 1),
                "subjects": len({s["subject_id"] for s in mine}),
                "divisions": len({s["division_id"] for s in mine}),
                "leave_taken": taken.get(uid, 0),
                "on_leave_today": uid in away,
            }
        )
    out.sort(key=lambda w: (-w["hours"], w["name"]))
    return {"date": today, "staff": out, "on_leave_today": [w["name"] for w in out if w["on_leave_today"]]}
