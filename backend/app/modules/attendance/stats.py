"""
Attendance percentages (plan 2.4).

Counted from `attendance_sessions` of the current academic year: a lecture counts for a student
when they were on its class list. Attended = not absent, or absent on a day covered by an active
exemption. Percentages are per subject; the college sets the minimum (default 75%) and the
warning level (default 80%) in College setup.
"""

import math
from collections import defaultdict
from datetime import date
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.modules.attendance import service
from app.modules.setup import service as setup
from app.modules.timetable import service as timetable

register_indexes(
    "attendance_alerts",
    [
        IndexModel(
            [
                ("student_id", ASCENDING),
                ("subject_id", ASCENDING),
                ("level", ASCENDING),
                ("academic_year_id", ASCENDING),
            ],
            unique=True,
        )
    ],
)

ALERT_MIN_LECTURES = 6  # no alerts on the first few lectures of a subject


def thresholds() -> tuple[int, int]:
    inst = setup.institution()
    return int(inst.get("attendance_min_percent") or 75), int(inst.get("attendance_warn_percent") or 80)


def can_miss(held: int, attended: int, minimum: int) -> int:
    """How many more lectures can be missed while staying at or above the minimum."""
    return max(0, math.floor(attended * 100 / minimum - held)) if minimum else held


def must_attend(held: int, attended: int, minimum: int) -> int:
    """How many lectures in a row must be attended to reach the minimum."""
    if minimum >= 100:
        return 0 if attended == held else 10**6
    return max(0, math.ceil((minimum * held - 100 * attended) / (100 - minimum)))


def _percent(attended: int, held: int) -> float | None:
    return round(attended * 100 / held, 1) if held else None


def _year_id(academic_year_id: str | None) -> ObjectId | None:
    if academic_year_id:
        return timetable.oid(academic_year_id, "Academic year", "academic_year_id")
    year = setup.current_year()
    return year["_id"] if year else None


def _exempt_days(student_ids: list[ObjectId]) -> dict[ObjectId, list[tuple[str, str]]]:
    days: dict[ObjectId, list[tuple[str, str]]] = defaultdict(list)
    for e in get_db().attendance_exemptions.find({"student_id": {"$in": student_ids}, "status": "active"}):
        days[e["student_id"]].append((e["from_date"], e["to_date"]))
    return days


def _is_exempt(ranges: list[tuple[str, str]], day: str) -> bool:
    return any(a <= day <= b for a, b in ranges)


def tally(student_ids: list[ObjectId], query: dict[str, Any]) -> dict[ObjectId, dict[ObjectId, dict[str, Any]]]:
    """student → subject → {held, attended, absent_days: [...]} for the sessions matching `query`."""
    exempt = _exempt_days(student_ids)
    wanted = set(student_ids)
    result: dict[ObjectId, dict[ObjectId, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"held": 0, "attended": 0, "lectures": []})
    )
    sessions = (
        get_db()
        .attendance_sessions.find(
            {**query, "roster": {"$in": student_ids}},
            {"roster": 1, "absent": 1, "subject_id": 1, "date": 1, "start": 1},
        )
        .sort([("date", ASCENDING), ("start", ASCENDING)])
    )
    for s in sessions:
        absent = set(s["absent"])
        for sid in wanted.intersection(s["roster"]):
            row = result[sid][s["subject_id"]]
            row["held"] += 1
            if sid not in absent:
                row["attended"] += 1
                mark = "present"
            elif _is_exempt(exempt.get(sid, []), s["date"]):
                row["attended"] += 1
                mark = "exempt"
            else:
                mark = "absent"
            row["lectures"].append({"date": s["date"], "start": s["start"], "mark": mark})
    return result


def _subjects(ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
    return {s["_id"]: s for s in get_db().subjects.find({"_id": {"$in": ids}}, {"code": 1, "name": 1})}


def student_summary(student: dict[str, Any], academic_year_id: str | None = None) -> dict[str, Any]:
    minimum, warn = thresholds()
    year_id = _year_id(academic_year_id)
    query: dict[str, Any] = {"academic_year_id": year_id} if year_id else {}
    rows = tally([student["_id"]], query).get(student["_id"], {})
    subjects = _subjects(list(rows))
    out = []
    calendar: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for subject_id, r in rows.items():
        sub = subjects.get(subject_id, {})
        pct = _percent(r["attended"], r["held"])
        out.append(
            {
                "subject_id": str(subject_id),
                "code": sub.get("code"),
                "name": sub.get("name"),
                "held": r["held"],
                "attended": r["attended"],
                "percent": pct,
                "status": _status(pct, minimum, warn),
                "can_miss": can_miss(r["held"], r["attended"], minimum),
                "must_attend": must_attend(r["held"], r["attended"], minimum),
            }
        )
        for x in r["lectures"]:
            calendar[x["date"]].append({"code": sub.get("code"), "start": x["start"], "mark": x["mark"]})
    out.sort(key=lambda x: x["code"] or "")
    held = sum(x["held"] for x in out)
    attended = sum(x["attended"] for x in out)
    overall = _percent(attended, held)
    return {
        "minimum": minimum,
        "warning": warn,
        "overall": {"held": held, "attended": attended, "percent": overall, "status": _status(overall, minimum, warn)},
        "subjects": out,
        "days": [
            {"date": d, "lectures": sorted(v, key=lambda x: x["start"])}
            for d, v in sorted(calendar.items(), reverse=True)
        ],
    }


def _status(pct: float | None, minimum: int, warn: int) -> str:
    if pct is None:
        return "none"
    return "critical" if pct < minimum else "warning" if pct < warn else "ok"


def my_attendance(ctx: AuthContext) -> dict[str, Any]:
    from app.modules.students import service as students

    return student_summary(students.my_student(ctx))


# --- class reports and defaulters -----------------------------------------------------------


def division_report(ctx: AuthContext, division_id: str, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    division = get_db().divisions.find_one({"_id": timetable.oid(division_id, "Class", "division_id")})
    if not division:
        raise AppError(422, "Class not found.", field="division_id")
    if not service.can_read_division(ctx, division):
        raise AppError(403, "You can't see this class's attendance.", "forbidden")
    minimum, warn = thresholds()
    year_id = _year_id(None)
    query: dict[str, Any] = {"division_id": division["_id"]}
    if year_id:
        query["academic_year_id"] = year_id
    if date_from or date_to:
        query["date"] = {
            **({"$gte": date_from.isoformat()} if date_from else {}),
            **({"$lte": date_to.isoformat()} if date_to else {}),
        }
    students = list(
        get_db().students.find(
            {"division_id": division["_id"], "status": "active"}, {"name": 1, "prn": 1, "roll_no": 1}
        )
    )
    students.sort(key=service._roll_key)
    rows = tally([s["_id"] for s in students], query)
    subject_ids = sorted({sub for r in rows.values() for sub in r}, key=str)
    subjects = _subjects(subject_ids)
    subject_ids.sort(key=lambda x: subjects.get(x, {}).get("code", ""))
    held_by_subject = {
        sub: get_db().attendance_sessions.count_documents({**query, "subject_id": sub}) for sub in subject_ids
    }
    out = []
    for s in students:
        r = rows.get(s["_id"], {})
        cells: dict[str, dict[str, Any]] = {}
        for sub in subject_ids:
            c = r.get(sub)
            pct = _percent(c["attended"], c["held"]) if c else None
            cells[str(sub)] = {
                "held": c["held"] if c else 0,
                "attended": c["attended"] if c else 0,
                "percent": pct,
                "status": _status(pct, minimum, warn),
            }
        held = sum(c["held"] for c in cells.values())
        attended = sum(c["attended"] for c in cells.values())
        overall = _percent(attended, held)
        out.append(
            {
                "student_id": str(s["_id"]),
                "name": s["name"],
                "prn": s["prn"],
                "roll_no": s.get("roll_no"),
                "subjects": cells,
                "overall": overall,
                "status": _status(overall, minimum, warn),
                "defaulter": any(c["status"] == "critical" for c in cells.values()),
            }
        )
    return {
        "class": timetable._division_label(division),
        "minimum": minimum,
        "warning": warn,
        "subjects": [
            {
                "id": str(sub),
                "code": subjects.get(sub, {}).get("code"),
                "name": subjects.get(sub, {}).get("name"),
                "held": held_by_subject[sub],
            }
            for sub in subject_ids
        ],
        "students": out,
    }


def readable_divisions(ctx: AuthContext) -> list[dict[str, Any]]:
    db = get_db()
    divisions = list(db.divisions.find({"status": {"$ne": "archived"}}))
    programmes = {p["_id"]: p for p in db.programmes.find({})}
    out = []
    for d in divisions:
        if service.can_read_division(ctx, d):
            out.append({"id": str(d["_id"]), "label": timetable._division_label(d, programmes.get(d["programme_id"]))})
    return sorted(out, key=lambda x: x["label"])


# --- daily alerts ---------------------------------------------------------------------------


def send_alerts(today: date | None = None) -> dict[str, int]:
    """Emails each student once per subject when they drop below the warning level, and again
    below the minimum. Run daily by Vercel Cron (GET /cron/attendance-alerts)."""
    db = get_db()
    minimum, warn = thresholds()
    year = setup.current_year()
    if not year:
        return {"students": 0, "sent": 0}
    inst = setup.institution()
    students = list(db.students.find({"status": "active"}, {"name": 1, "email": 1, "user_id": 1}))
    rows = tally([s["_id"] for s in students], {"academic_year_id": year["_id"]})
    sent = 0
    for s in students:
        email = s.get("email") or (db.users.find_one({"_id": s.get("user_id")}, {"email": 1}) or {}).get("email")
        subjects = _subjects(list(rows.get(s["_id"], {})))
        for subject_id, r in rows.get(s["_id"], {}).items():
            if r["held"] < ALERT_MIN_LECTURES:
                continue
            pct = _percent(r["attended"], r["held"]) or 0.0
            level = "critical" if pct < minimum else "warning" if pct < warn else None
            if not level:
                continue
            try:
                db.attendance_alerts.insert_one(
                    {
                        "student_id": s["_id"],
                        "subject_id": subject_id,
                        "level": level,
                        "academic_year_id": year["_id"],
                        "percent": pct,
                        "at": clock.now(),
                        "emailed": bool(email),
                    }
                )
            except DuplicateKeyError:
                continue  # already told about this level
            if not email:
                continue
            sub = subjects.get(subject_id, {})
            need = must_attend(r["held"], r["attended"], minimum)
            if level == "critical":
                advice = (
                    f"This is below the minimum of {minimum}%. Attend the next {need} lectures in a row to reach it."
                )
            else:
                spare = can_miss(r["held"], r["attended"], minimum)
                advice = f"The minimum is {minimum}%. You can miss {spare} more lectures."
            text = (
                f"Dear {s['name']},\n\n"
                f"Your attendance in {sub.get('code')} {sub.get('name')} is {pct}% "
                f"({r['attended']} of {r['held']} lectures).\n{advice}\n\n"
                "If you were on medical leave or official duty, submit the document at the college office.\n\n"
                f"{inst.get('name') or 'CollegeConnect'}"
            )
            subject_line = (
                f"{'Low attendance' if level == 'critical' else 'Attendance warning'}: {sub.get('code')} {pct}%"
            )
            if send_email(email, subject_line, text):
                sent += 1
    audit.record("attendance.alerts_sent", details={"sent": sent, "students": len(students)})
    return {"students": len(students), "sent": sent}
