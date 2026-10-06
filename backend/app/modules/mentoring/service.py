"""
Early warning and mentoring (spec U10, plan 4.4).

Configurable, explainable rules (attendance below the minimum or falling, low internal marks,
backlogs, fees long overdue) give each active student a risk level with the reasons listed.
They are worked out by the daily job (and on demand) into `risk_flags`, one small document per
student, so pages stay fast. Only the student's mentor, their HOD and the Principal see them; the
student and parents never do, and nothing happens automatically: it is a prompt for a mentor to
talk to the student, with counselling notes kept here.

A student's mentor is set by the office (any class) or the HOD (their department).
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReplaceOne

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.money import format_inr
from app.core.rbac import P
from app.modules.attendance import stats
from app.modules.fees import ledger
from app.modules.marks.service import VISIBLE_TO_STUDENTS
from app.modules.mentoring.schemas import AssignIn, NoteIn, RiskRules
from app.modules.setup import service as setup
from app.modules.students import service as students
from app.modules.timetable import service as timetable

register_indexes(
    "risk_flags",
    [
        IndexModel([("level", ASCENDING), ("department_id", ASCENDING)]),
        IndexModel([("mentor_id", ASCENDING)]),
    ],
)
register_indexes("mentor_notes", [IndexModel([("student_id", ASCENDING), ("at", DESCENDING)])])
register_indexes("students", [IndexModel([("mentor_id", ASCENDING)])])

SETTINGS_ID = "early_warning"
RECENT_DAYS = 28
LEVEL_ORDER = {"high": 0, "medium": 1, "none": 2}
MENTOR_ROLES = {"mentor", "hod", "faculty"}


def rules() -> dict[str, Any]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID})
    if doc:
        return RiskRules(**{k: v for k, v in doc.items() if k != "_id"}).model_dump()
    minimum, _ = stats.thresholds()
    return RiskRules(attendance_below={"on": True, "value": minimum}).model_dump()  # type: ignore[arg-type]


def save_rules(ctx: AuthContext, body: RiskRules) -> dict[str, Any]:
    data = body.model_dump()
    get_db().settings.update_one({"_id": SETTINGS_ID}, {"$set": data}, upsert=True)
    audit.record("risk.rules_updated", actor_id=ctx.user_id, details=data)
    return rules()


# --- working it out -------------------------------------------------------------------------


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _attendance(ids: list[ObjectId], year_id: ObjectId, today: date) -> dict[ObjectId, dict[str, Any]]:
    cutoff = (today - timedelta(days=RECENT_DAYS)).isoformat()
    out: dict[ObjectId, dict[str, Any]] = {}
    for sid, subjects in stats.tally(ids, {"academic_year_id": year_id}).items():
        held = attended = recent_held = recent_attended = 0
        for r in subjects.values():
            held += r["held"]
            attended += r["attended"]
            for lec in r["lectures"]:
                if lec["date"] >= cutoff:
                    recent_held += 1
                    recent_attended += lec["mark"] != "absent"
        out[sid] = {
            "overall": _pct(attended, held),
            "recent": _pct(recent_attended, recent_held),
            "before": _pct(attended - recent_attended, held - recent_held),
            "held": held,
        }
    return out


def _low_marks(year_id: ObjectId, threshold: float) -> dict[str, list[str]]:
    """student id (str) → subjects where the published internal marks are below the threshold."""
    db = get_db()
    out: dict[str, list[str]] = defaultdict(list)
    for sheet in db.marks_sheets.find({"academic_year_id": year_id, "status": {"$in": sorted(VISIBLE_TO_STUDENTS)}}):
        scheme = db.assessment_schemes.find_one({"_id": sheet["scheme_id"]}, {"components": 1})
        subject = db.subjects.find_one({"_id": sheet["subject_id"]}, {"code": 1})
        if not scheme or not subject:
            continue
        for sid, entry in sheet.get("marks", {}).items():
            got = out_of = 0.0
            for c in scheme["components"]:
                v = entry.get(c["key"])
                if v is None:
                    continue
                got += 0 if v == "AB" else float(v)
                out_of += c["max"]
            pct = _pct(got, out_of)
            if pct is not None and pct < threshold:
                out[sid].append(f"{subject['code']} {got:g}/{out_of:g}")
    return out


def _backlogs(ids: list[ObjectId]) -> dict[ObjectId, list[str]]:
    db = get_db()
    results = list(
        db.results.find(
            {"student_id": {"$in": ids}}, {"student_id": 1, "session_id": 1, "exam_order": 1, "subjects": 1}
        )
    )
    published = {
        s["_id"]
        for s in db.exam_sessions.find(
            {"_id": {"$in": list({r["session_id"] for r in results})}, "results_published": True}, {"_id": 1}
        )
    }
    latest: dict[ObjectId, dict[ObjectId, dict[str, Any]]] = defaultdict(dict)
    for r in sorted((r for r in results if r["session_id"] in published), key=lambda r: r.get("exam_order", 0)):
        for s in r["subjects"]:
            latest[r["student_id"]][s["subject_id"]] = s
    return {sid: sorted(s["code"] for s in subs.values() if not s["passed"]) for sid, subs in latest.items()}


def _fees(ids: list[ObjectId], year_id: ObjectId, today: date) -> dict[ObjectId, tuple[int, int]]:
    """student → (overdue amount, days since the oldest overdue installment fell due)."""
    rows: dict[ObjectId, list[dict[str, Any]]] = defaultdict(list)
    for e in (
        get_db().ledger_entries.find({"academic_year_id": year_id, "student_id": {"$in": ids}}).sort("at", ASCENDING)
    ):
        rows[e["student_id"]].append(e)
    out = {}
    for sid, entries in rows.items():
        info = ledger.summary(entries, today)
        late = [i for i in info["installments"] if i["overdue"]]
        if late:
            oldest = min(date.fromisoformat(i["due_date"]) for i in late)
            out[sid] = (info["overdue"], (today - oldest).days)
    return out


def compute() -> dict[str, int]:
    """Works out every active student's risk level and reasons (the daily job; also on demand)."""
    year = setup.current_year()
    db = get_db()
    if not year:
        return {"students": 0, "high": 0, "medium": 0}
    today = clock.today()
    r = rules()
    people = list(db.students.find({"status": "active"}, {"name": 1, "prn": 1, "division_id": 1, "mentor_id": 1}))
    ids = [s["_id"] for s in people]
    divisions = {d["_id"]: d for d in db.divisions.find({})}
    programmes = {p["_id"]: p for p in db.programmes.find({}, {"code": 1, "year_labels": 1, "department_id": 1})}
    attendance = _attendance(ids, year["_id"], today)
    marks = _low_marks(year["_id"], r["marks_below"]["value"]) if r["marks_below"]["on"] else {}
    backlogs = _backlogs(ids) if r["backlogs"]["on"] else {}
    fees = _fees(ids, year["_id"], today) if r["fee_overdue"]["on"] else {}
    ops, counts = [], {"high": 0, "medium": 0}
    for s in people:
        reasons: list[dict[str, str]] = []
        att = attendance.get(s["_id"], {})
        if (
            r["attendance_below"]["on"]
            and att.get("overall") is not None
            and att["overall"] < r["attendance_below"]["value"]
        ):
            reasons.append(
                {
                    "rule": "attendance_below",
                    "text": f"Attendance {att['overall']:g}% (minimum {r['attendance_below']['value']:g}%)",
                }
            )
        if (
            r["attendance_drop"]["on"]
            and att.get("recent") is not None
            and att.get("before") is not None
            and att["before"] - att["recent"] >= r["attendance_drop"]["value"]
        ):
            reasons.append(
                {
                    "rule": "attendance_drop",
                    "text": f"Attendance fell from {att['before']:g}% to {att['recent']:g}% in the last 4 weeks",
                }
            )
        low = marks.get(str(s["_id"]), [])
        if low:
            reasons.append(
                {
                    "rule": "marks_below",
                    "text": f"Internal marks below {r['marks_below']['value']:g}% in " + ", ".join(low),
                }
            )
        back = backlogs.get(s["_id"], [])
        if back and len(back) >= r["backlogs"]["value"]:
            reasons.append({"rule": "backlogs", "text": f"{len(back)} subject(s) to clear: {', '.join(back)}"})
        fee = fees.get(s["_id"])
        if fee and fee[1] >= r["fee_overdue"]["value"]:
            reasons.append(
                {"rule": "fee_overdue", "text": f"Fees of {format_inr(fee[0], 'Rs. ')} overdue for {fee[1]} days"}
            )
        level = "high" if len(reasons) >= 2 else "medium" if reasons else "none"
        if level != "none":
            counts[level] += 1
        d = divisions.get(s.get("division_id"))
        p = programmes.get(d["programme_id"]) if d else None
        ops.append(
            ReplaceOne(
                {"_id": s["_id"]},
                {
                    "name": s["name"],
                    "prn": s.get("prn"),
                    "division_id": s.get("division_id"),
                    "class": timetable._division_label(d, p) if d else None,
                    "department_id": (p or {}).get("department_id"),
                    "mentor_id": s.get("mentor_id"),
                    "level": level,
                    "reasons": reasons,
                    "signals": {
                        "attendance": att.get("overall"),
                        "attendance_recent": att.get("recent"),
                        "backlogs": len(back),
                        "fees_overdue": fee[0] if fee else 0,
                    },
                    "computed_at": clock.now(),
                },
                upsert=True,
            )
        )
    if ops:
        db.risk_flags.bulk_write(ops, ordered=False)
    db.risk_flags.delete_many({"_id": {"$nin": ids}})
    return {"students": len(ids), **counts}


def daily() -> dict[str, int]:
    return compute()


# --- who sees what --------------------------------------------------------------------------


def scope(ctx: AuthContext) -> dict[str, Any]:
    """Risk flags this person may see: all (Principal), their department (HOD), their mentees."""
    perms = ctx.permissions
    if P.RISK_READ in perms:
        return {}
    allowed: list[dict[str, Any]] = []
    if P.RISK_READ_DEPT in perms and ctx.user.get("department_id"):
        allowed.append({"department_id": ctx.user["department_id"]})
    if P.MENTEES in perms:
        allowed.append({"mentor_id": ctx.user_id})
    if not allowed:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return {"$or": allowed}


def _names(ids: list[ObjectId]) -> dict[ObjectId, str]:
    return {u["_id"]: u["name"] for u in get_db().users.find({"_id": {"$in": ids}}, {"name": 1})}


def _view(f: dict[str, Any], mentors: dict[ObjectId, str], notes: dict[ObjectId, dict[str, Any]]) -> dict[str, Any]:
    n = notes.get(f["_id"], {})
    return {
        "student_id": str(f["_id"]),
        "name": f["name"],
        "prn": f.get("prn"),
        "class": f.get("class"),
        "level": f["level"],
        "reasons": [r["text"] for r in f.get("reasons", [])],
        "signals": f.get("signals", {}),
        "mentor": mentors.get(f.get("mentor_id")) if f.get("mentor_id") else None,  # type: ignore[arg-type]
        "notes": n.get("count", 0),
        "last_note_at": n.get("last"),
        "follow_up_on": n.get("follow_up_on"),
        "computed_at": f.get("computed_at"),
    }


def _views(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    db = get_db()
    mentors = _names(list({f["mentor_id"] for f in flags if f.get("mentor_id")}))
    notes: dict[ObjectId, dict[str, Any]] = {}
    for n in db.mentor_notes.aggregate(
        [
            {"$match": {"student_id": {"$in": [f["_id"] for f in flags]}}},
            {"$sort": {"at": 1}},
            {
                "$group": {
                    "_id": "$student_id",
                    "count": {"$sum": 1},
                    "last": {"$last": "$at"},
                    "follow_up_on": {"$last": "$follow_up_on"},
                }
            },
        ]
    ):
        notes[n["_id"]] = n
    rows = [_view(f, mentors, notes) for f in flags]
    rows.sort(key=lambda r: (LEVEL_ORDER[r["level"]], r["class"] or "", r["prn"] or ""))
    return rows


def at_risk(ctx: AuthContext, level: str | None, division_id: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {
        **scope(ctx),
        "level": level if level in {"high", "medium"} else {"$in": ["high", "medium"]},
    }
    if division_id:
        query["division_id"] = students.oid(division_id, "Class")
    flags = list(get_db().risk_flags.find(query).limit(500))
    last = get_db().risk_flags.find_one({}, {"computed_at": 1}, sort=[("computed_at", DESCENDING)])
    return {"students": _views(flags), "computed_at": last.get("computed_at") if last else None, "rules": rules()}


def mentees(ctx: AuthContext) -> dict[str, Any]:
    if P.MENTEES not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    db = get_db()
    mine = list(db.students.find({"mentor_id": ctx.user_id, "status": "active"}, {"_id": 1, "name": 1, "prn": 1}))
    flags = {f["_id"]: f for f in db.risk_flags.find({"_id": {"$in": [s["_id"] for s in mine]}})}
    rows = _views(
        [
            flags.get(s["_id"])
            or {"_id": s["_id"], "name": s["name"], "prn": s.get("prn"), "level": "none", "reasons": []}
            for s in mine
        ]
    )
    return {
        "students": rows,
        "high": sum(r["level"] == "high" for r in rows),
        "medium": sum(r["level"] == "medium" for r in rows),
    }


def _flag_in_scope(ctx: AuthContext, student_id: str) -> dict[str, Any]:
    sid = students.oid(student_id)
    f = get_db().risk_flags.find_one({"_id": sid, **scope(ctx)})
    if not f:
        s = get_db().students.find_one({"_id": sid, "mentor_id": ctx.user_id}, {"name": 1, "prn": 1})
        if not s:
            raise AppError(404, "Student not found.")
        f = {"_id": sid, "name": s["name"], "prn": s.get("prn"), "level": "none", "reasons": []}
    return f


def detail(ctx: AuthContext, student_id: str) -> dict[str, Any]:
    f = _flag_in_scope(ctx, student_id)
    notes = list(get_db().mentor_notes.find({"student_id": f["_id"]}).sort("at", DESCENDING).limit(100))
    return {
        **_views([f])[0],
        "history": [
            {
                "id": str(n["_id"]),
                "at": n["at"],
                "by": n["by_name"],
                "text": n["text"],
                "follow_up_on": n.get("follow_up_on"),
            }
            for n in notes
        ],
    }


def add_note(ctx: AuthContext, student_id: str, body: NoteIn) -> dict[str, Any]:
    f = _flag_in_scope(ctx, student_id)
    get_db().mentor_notes.insert_one(
        {
            "student_id": f["_id"],
            "by": ctx.user_id,
            "by_name": ctx.user["name"],
            "at": clock.now(),
            "text": body.text.strip(),
            "follow_up_on": body.follow_up_on,
            "level_then": f["level"],
        }
    )
    # The note itself stays out of the audit log: it is confidential counselling.
    audit.record("mentoring.note_added", actor_id=ctx.user_id, target_type="student", target_id=f["_id"])
    return detail(ctx, student_id)


# --- assigning mentors ----------------------------------------------------------------------


def _assign_scope(ctx: AuthContext) -> dict[str, Any]:
    if P.MENTOR_ASSIGN not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    if P.STUDENTS_MANAGE in ctx.permissions:
        return {}
    dept = ctx.user.get("department_id")
    if not dept:
        raise AppError(403, "You are not linked to a department.", "forbidden")
    programmes = [p["_id"] for p in get_db().programmes.find({"department_id": dept}, {"_id": 1})]
    return {"programme_id": {"$in": programmes}}


def assignments(ctx: AuthContext, division_id: str) -> dict[str, Any]:
    db = get_db()
    query = {**_assign_scope(ctx), "division_id": students.oid(division_id, "Class"), "status": "active"}
    rows = list(db.students.find(query, {"name": 1, "prn": 1, "mentor_id": 1}).sort("prn", ASCENDING))
    mentor_query: dict[str, Any] = {"kind": "staff", "status": "active", "roles": {"$in": sorted(MENTOR_ROLES)}}
    if P.STUDENTS_MANAGE not in ctx.permissions:
        mentor_query["department_id"] = ctx.user.get("department_id")
    mentors = list(db.users.find(mentor_query, {"name": 1}).sort("name", ASCENDING))
    names = {m["_id"]: m["name"] for m in mentors}
    names.update(_names([r["mentor_id"] for r in rows if r.get("mentor_id") and r["mentor_id"] not in names]))
    return {
        "students": [
            {
                "id": str(r["_id"]),
                "name": r["name"],
                "prn": r.get("prn"),
                "mentor_id": str(r["mentor_id"]) if r.get("mentor_id") else None,
                "mentor": names.get(r["mentor_id"]) if r.get("mentor_id") else None,
            }
            for r in rows
        ],
        "mentors": [{"id": str(m["_id"]), "name": m["name"]} for m in mentors],
    }


def assign(ctx: AuthContext, body: AssignIn, ip: str) -> dict[str, Any]:
    db = get_db()
    mentor_id = None
    if body.mentor_id:
        mentor = db.users.find_one(
            {
                "_id": students.oid(body.mentor_id, "Mentor"),
                "kind": "staff",
                "status": "active",
                "roles": {"$in": sorted(MENTOR_ROLES)},
            }
        )
        if not mentor:
            raise AppError(422, "Pick a teacher as the mentor.", field="mentor_id")
        mentor_id = mentor["_id"]
    ids = [students.oid(s) for s in body.student_ids]
    query = {**_assign_scope(ctx), "_id": {"$in": ids}}
    if db.students.count_documents(query) != len(set(ids)):
        raise AppError(403, "Some of these students are not in your department.", "forbidden")
    db.students.update_many(query, {"$set": {"mentor_id": mentor_id}})
    db.risk_flags.update_many({"_id": {"$in": ids}}, {"$set": {"mentor_id": mentor_id}})
    audit.record(
        "mentoring.assigned",
        actor_id=ctx.user_id,
        ip=ip,
        details={"mentor_id": str(mentor_id) if mentor_id else None, "students": len(ids)},
    )
    return {"updated": len(ids)}


def counts(ctx: AuthContext) -> dict[str, int] | None:
    """For dashboards: at-risk students this person may see."""
    try:
        query = scope(ctx)
    except AppError:
        return None
    db = get_db()
    return {lv: db.risk_flags.count_documents({**query, "level": lv}) for lv in ("high", "medium")}
