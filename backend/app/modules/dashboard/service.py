"""
Staff home dashboards (spec R2–R8, plan 2.11): one call returns the sections the signed-in
person's roles allow. Each section is small and cheap (counts and short lists), so the home
page stays fast on the free tiers.
"""

from collections import defaultdict
from typing import Any

from bson import ObjectId

from app.core import clock
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.rbac import P
from app.modules.attendance import service as attendance
from app.modules.attendance import stats
from app.modules.marks import service as marks
from app.modules.timetable import service as timetable


def _teaching(ctx: AuthContext) -> dict[str, Any]:
    today = attendance.today(ctx, clock.today())
    lectures = [
        {
            "slot_id": x["slot_id"],
            "date": x["date"],
            "start": x["start"],
            "end": x["end"],
            "code": x["subject_code"],
            "class": x["division"],
            "status": x["status"],
            "takeable": x["takeable"],
            "taken": x["session"] is not None,
        }
        for x in today["lectures"]
    ]
    tasks = []
    try:
        for r in marks.my_classes(ctx):
            if r["has_scheme"] and r["status"] == "draft":
                tasks.append(
                    {
                        "division_id": r["division_id"],
                        "subject_id": r["subject_id"],
                        "label": f"{r['class']} · {r['code']}",
                        "status": r["status_label"],
                        "complete": r["complete"],
                        "students": r["students"],
                        "deadline": r["deadline"],
                    }
                )
    except Exception:  # noqa: BLE001 - no current year yet: no marks tasks
        tasks = []
    return {
        "holiday": today["holiday"],
        "lectures": lectures,
        "marks_tasks": sorted(tasks, key=lambda t: t["deadline"] or "9999")[:8],
    }


def _department_divisions(dept: ObjectId) -> list[dict[str, Any]]:
    db = get_db()
    programmes = [p["_id"] for p in db.programmes.find({"department_id": dept}, {"_id": 1})]
    return list(db.divisions.find({"programme_id": {"$in": programmes}, "status": {"$ne": "archived"}}))


def _hod(ctx: AuthContext) -> dict[str, Any] | None:
    dept = ctx.user.get("department_id")
    if not dept:
        return None
    db = get_db()
    divisions = _department_divisions(dept)
    division_ids = [d["_id"] for d in divisions]
    minimum, _ = stats.thresholds()
    year = marks.current_year_id() if db.academic_years.find_one({"is_current": True}) else None
    classes = []
    for d in divisions:
        students = [s["_id"] for s in db.students.find({"division_id": d["_id"], "status": "active"}, {"_id": 1})]
        rows = stats.tally(students, {"division_id": d["_id"], **({"academic_year_id": year} if year else {})})
        held = sum(r["held"] for s in rows.values() for r in s.values())
        attended = sum(r["attended"] for s in rows.values() for r in s.values())
        defaulters = sum(
            1 for s in rows.values() if any(r["held"] and r["attended"] * 100 / r["held"] < minimum for r in s.values())
        )
        classes.append(
            {
                "division_id": str(d["_id"]),
                "class": timetable._division_label(d),
                "students": len(students),
                "attendance": round(attended * 100 / held, 1) if held else None,
                "defaulters": defaulters,
            }
        )
    workload: dict[ObjectId, float] = defaultdict(float)
    for s in db.timetable_slots.find(
        {"division_id": {"$in": division_ids}, "status": "active"},
        {"faculty_ids": 1, "start": 1, "end": 1, "valid_to": 1},
    ):
        if s["valid_to"] < clock.today().isoformat():
            continue
        hours = (int(s["end"][:2]) * 60 + int(s["end"][3:]) - int(s["start"][:2]) * 60 - int(s["start"][3:])) / 60
        for f in s["faculty_ids"]:
            workload[f] += hours
    names = {u["_id"]: u["name"] for u in db.users.find({"_id": {"$in": list(workload)}}, {"name": 1})}
    return {
        "classes": sorted(classes, key=lambda c: c["class"]),
        "attendance_requests": db.attendance_edit_requests.count_documents(
            {"status": "pending", "division_id": {"$in": division_ids}}
        ),
        "marks_to_approve": db.marks_sheets.count_documents(
            {"status": "published", "division_id": {"$in": division_ids}}
        ),
        "workload": sorted(
            ({"name": names.get(k, "?"), "hours": round(v, 1)} for k, v in workload.items()), key=lambda w: -w["hours"]
        ),
    }


def _exam_cell() -> dict[str, Any]:
    db = get_db()
    sessions = []
    for s in db.exam_sessions.find({}).sort("created_at", -1).limit(5):
        sessions.append(
            {
                "id": str(s["_id"]),
                "name": s["name"],
                "form_deadline": s["form_deadline"],
                "to_verify": db.exam_forms.count_documents({"session_id": s["_id"], "status": "submitted"}),
                "verified": db.exam_forms.count_documents({"session_id": s["_id"], "status": "verified"}),
                "results_published": bool(s.get("results_published")),
            }
        )
    by_status: dict[str, int] = defaultdict(int)
    for r in db.marks_sheets.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        by_status[r["_id"]] = r["n"]
    return {
        "sessions": sessions,
        "marks": dict(by_status),
        "revaluations": db.revaluations.count_documents({"status": "requested"}),
        "subjects_without_scheme": max(
            0, db.subjects.count_documents({"status": {"$ne": "archived"}}) - db.assessment_schemes.count_documents({})
        ),
    }


def _office() -> dict[str, Any]:
    db = get_db()
    today = clock.today().isoformat()
    open_q = {"status": {"$in": ["requested", "verified", "signed"]}}
    return {
        "certificates_open": db.certificate_requests.count_documents(open_q),
        "certificates_overdue": db.certificate_requests.count_documents({**open_q, "due_date": {"$lt": today}}),
        "certificates_to_issue": db.certificate_requests.count_documents({"status": "signed"}),
        "corrections": db.student_change_requests.count_documents({"status": "pending"}),
        "documents": db.students.count_documents({"documents": {"$elemMatch": {"status": "pending"}}}),
    }


def _principal(ctx: AuthContext) -> dict[str, Any]:
    db = get_db()
    today = clock.today().isoformat()
    minimum, _ = stats.thresholds()
    return {
        "approvals": db.approvals.count_documents({"status": "pending"})
        if P.APPROVALS_DECIDE in ctx.permissions
        else 0,
        "exports": db.export_requests.count_documents({"status": "pending"}),
        "certificates_to_sign": db.certificate_requests.count_documents(
            {"status": "verified", "type": {"$in": ["tc", "migration"]}}
        ),
        "certificates_overdue": db.certificate_requests.count_documents(
            {"status": {"$in": ["requested", "verified", "signed"]}, "due_date": {"$lt": today}}
        ),
        "attendance_minimum": minimum,
    }


def dashboard(ctx: AuthContext) -> dict[str, Any]:
    perms = ctx.permissions
    out: dict[str, Any] = {}
    if P.ATTENDANCE_TAKE in perms:
        out["teaching"] = _teaching(ctx)
    if P.MARKS_APPROVE in perms or P.ATTENDANCE_APPROVE in perms:
        out["hod"] = _hod(ctx)
    if P.EXAMS_MANAGE in perms:
        out["exam_cell"] = _exam_cell()
    if P.CERT_MANAGE in perms:
        out["office"] = _office()
    if P.CERT_SIGN_PRINCIPAL in perms or P.APPROVALS_DECIDE in perms:
        out["principal"] = _principal(ctx)
    return out
