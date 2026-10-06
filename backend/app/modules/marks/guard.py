"""
University Upload Guard (unique feature U7, plan 2.6).

Before the university's internal-marks deadline, a checklist per class and subject:
- missing: students on the class list without every part entered;
- above maximum: a mark above its part's maximum (possible if the scheme was lowered later);
- absent but marked: a mark entered for a test the attendance says the student missed
  (needs the part's test date);
- not eligible: below the attendance minimum in the subject (and, from 2.7, no eligible exam
  form).
The export is the university's internal-marks upload: one row per student, whole marks (rounded
up), "AB" when absent for every part. `check_file` validates an export before it is uploaded.
"""

import csv
import io
from datetime import date
from typing import Any

from bson import ObjectId

from app.core import clock
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.attendance import stats
from app.modules.marks import service
from app.modules.timetable import service as timetable

HEADER = ["PRN", "Student name", "Subject code", "Internal marks", "Maximum"]
ISSUES = {
    "missing": "Marks missing",
    "above_max": "Above the maximum",
    "absent_marked": "Marked but absent on the test day",
    "ineligible": "Not eligible for the exam",
}


def _division(division_id: str) -> dict[str, Any]:
    division = get_db().divisions.find_one({"_id": service._oid(division_id, "Class", "division_id")})
    if not division:
        raise AppError(422, "Class not found.", field="division_id")
    return division


def _require_view(ctx: AuthContext, division: dict[str, Any]) -> None:
    if not (P.EXAMS_MANAGE in ctx.permissions or service.is_hod_for(ctx, division)):
        raise AppError(403, "Only the Exam Cell and the HOD see the Upload Guard.", "forbidden")


def ineligible_students(
    division_id: ObjectId, subject_id: ObjectId, student_ids: list[ObjectId]
) -> dict[ObjectId, str]:
    """student → reason they may not sit the exam (attendance now; exam forms from 2.7)."""
    minimum, _ = stats.thresholds()
    year_id = service.current_year_id()
    rows = stats.tally(student_ids, {"academic_year_id": year_id, "subject_id": subject_id, "division_id": division_id})
    reasons: dict[ObjectId, str] = {}
    for sid in student_ids:
        r = rows.get(sid, {}).get(subject_id)
        if r and r["held"]:
            pct = round(r["attended"] * 100 / r["held"], 1)
            if pct < minimum:
                reasons[sid] = f"Attendance {pct}% (minimum {minimum}%)"
    for hook in EXTRA_ELIGIBILITY:
        for sid, why in hook(division_id, subject_id, student_ids).items():
            reasons.setdefault(sid, why)
    return reasons


# Later modules (exam forms) add checks here: fn(division_id, subject_id, student_ids) → {student: reason}
EXTRA_ELIGIBILITY: list[Any] = []


def check(division: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    year_id = service.current_year_id()
    scheme = db.assessment_schemes.find_one({"subject_id": subject["_id"], "academic_year_id": year_id})
    students = service.class_students(division["_id"])
    sheet = db.marks_sheets.find_one({"scheme_id": scheme["_id"], "division_id": division["_id"]}) if scheme else None
    marks = (sheet or {}).get("marks", {})
    issues: list[dict[str, Any]] = []

    def add(kind: str, s: dict[str, Any], detail: str) -> None:
        issues.append(
            {
                "kind": kind,
                "label": ISSUES[kind],
                "student_id": str(s["_id"]),
                "name": s["name"],
                "prn": s["prn"],
                "detail": detail,
            }
        )

    absent_on: dict[str, set[ObjectId]] = {}
    for c in (scheme or {}).get("components", []):
        if c.get("held_on"):
            absent: set[ObjectId] = set()
            for session in db.attendance_sessions.find(
                {"division_id": division["_id"], "subject_id": subject["_id"], "date": c["held_on"]}, {"absent": 1}
            ):
                absent |= set(session["absent"])
            absent_on[c["key"]] = absent
    for s in students:
        entry = marks.get(str(s["_id"]), {})
        if not scheme:
            continue
        missing = [c["name"] for c in scheme["components"] if c["key"] not in entry]
        if missing:
            add("missing", s, ", ".join(missing))
        for c in scheme["components"]:
            v = entry.get(c["key"])
            if isinstance(v, (int, float)) and v > c["max"]:
                add("above_max", s, f"{c['name']}: {v:g} of {c['max']:g}")
            if isinstance(v, (int, float)) and s["_id"] in absent_on.get(c["key"], set()):
                add("absent_marked", s, f"{c['name']} on {c['held_on']}: {v:g}")
    for sid, why in ineligible_students(division["_id"], subject["_id"], [s["_id"] for s in students]).items():
        s = next(x for x in students if x["_id"] == sid)
        add("ineligible", s, why)
    deadline = (scheme or {}).get("deadline")
    return {
        "class": timetable._division_label(division),
        "division_id": str(division["_id"]),
        "subject_id": str(subject["_id"]),
        "code": subject["code"],
        "name": subject["name"],
        "has_scheme": bool(scheme),
        "status": (sheet or {}).get("status", "draft"),
        "status_label": service.STATUS_LABELS[(sheet or {}).get("status", "draft")],
        "deadline": deadline,
        "days_left": (date.fromisoformat(deadline) - clock.today()).days if deadline else None,
        "students": len(students),
        "counts": {k: sum(1 for i in issues if i["kind"] == k) for k in ISSUES},
        "issues": issues,
        "ready": bool(scheme) and not any(i["kind"] in ("missing", "above_max") for i in issues),
    }


def detail(ctx: AuthContext, division_id: str, subject_id: str) -> dict[str, Any]:
    division = _division(division_id)
    _require_view(ctx, division)
    return check(division, service._subject(subject_id))


def dashboard(ctx: AuthContext) -> dict[str, Any]:
    """Every class-subject of the year (HOD: their department), with counts, grouped by department."""
    db = get_db()
    if P.EXAMS_MANAGE not in ctx.permissions and P.MARKS_APPROVE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell and the HOD see the Upload Guard.", "forbidden")
    rows = service.department_sheets(ctx)
    divisions = {d["_id"]: d for d in db.divisions.find({"_id": {"$in": [ObjectId(r["division_id"]) for r in rows]}})}
    subjects = {s["_id"]: s for s in db.subjects.find({"_id": {"$in": [ObjectId(r["subject_id"]) for r in rows]}})}
    departments = {d["_id"]: d for d in db.departments.find({})}
    programmes = {p["_id"]: p for p in db.programmes.find({}, {"department_id": 1})}
    out = []
    for r in rows:
        division = divisions[ObjectId(r["division_id"])]
        if P.EXAMS_MANAGE not in ctx.permissions and not service.is_hod_for(ctx, division):
            continue
        c = check(division, subjects[ObjectId(r["subject_id"])])
        dept = departments.get(programmes.get(division["programme_id"], {}).get("department_id"), {})
        out.append({**{k: v for k, v in c.items() if k != "issues"}, "department": dept.get("name", "—")})
    by_dept: dict[str, dict[str, int]] = {}
    for r in out:
        d = by_dept.setdefault(r["department"], {"subjects": 0, "ready": 0, "locked": 0})
        d["subjects"] += 1
        d["ready"] += int(r["ready"])
        d["locked"] += int(r["status"] == "locked")
    return {"rows": out, "departments": [{"name": k, **v} for k, v in sorted(by_dept.items())]}


def export_csv(ctx: AuthContext, division_id: str, subject_id: str) -> tuple[str, bytes]:
    if P.EXAMS_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell exports marks for the university.", "forbidden")
    division = _division(division_id)
    subject = service._subject(subject_id)
    result = check(division, subject)
    if not result["ready"]:
        raise AppError(409, "Fix the missing and above-maximum marks first (see the Upload Guard).", "not_ready")
    db = get_db()
    scheme = db.assessment_schemes.find_one(
        {"subject_id": subject["_id"], "academic_year_id": service.current_year_id()}
    )
    assert scheme is not None
    sheet = db.marks_sheets.find_one({"scheme_id": scheme["_id"], "division_id": division["_id"]}) or {"marks": {}}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADER)
    for s in service.class_students(division["_id"]):
        entry = sheet["marks"].get(str(s["_id"]), {})
        all_absent = all(entry.get(c["key"]) == "AB" for c in scheme["components"])
        total = service.total_of(entry, scheme) or 0
        writer.writerow(
            [
                s["prn"],
                s["name"],
                subject["code"],
                "AB" if all_absent else service.round_up(total),
                subject["max_internal"],
            ]
        )
    label = timetable._division_label(division).replace(" ", "-")
    return f"internal-marks-{subject['code']}-{label}.csv", out.getvalue().encode("utf-8")


def check_file(ctx: AuthContext, division_id: str, subject_id: str, data: bytes) -> dict[str, Any]:
    """Validates an upload file against the class list before it goes to the university portal."""
    if P.EXAMS_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell checks university files.", "forbidden")
    division = _division(division_id)
    subject = service._subject(subject_id)
    problems: list[str] = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"ok": False, "problems": ["The file isn't UTF-8 text (save it as CSV UTF-8)."]}
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or [h.strip() for h in rows[0]] != HEADER:
        return {"ok": False, "problems": [f"The first row must be: {', '.join(HEADER)}."]}
    expected = {s["prn"]: s for s in service.class_students(division["_id"])}
    seen: set[str] = set()
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(HEADER):
            problems.append(f"Row {n}: expected {len(HEADER)} columns.")
            continue
        prn, _name, code, mark, maximum = (x.strip() for x in row)
        if prn not in expected:
            problems.append(f"Row {n}: {prn} isn't in {timetable._division_label(division)}.")
        if prn in seen:
            problems.append(f"Row {n}: {prn} appears twice.")
        seen.add(prn)
        if code != subject["code"]:
            problems.append(f"Row {n}: subject code {code} should be {subject['code']}.")
        if maximum != str(subject["max_internal"]):
            problems.append(f"Row {n}: maximum {maximum} should be {subject['max_internal']}.")
        if mark != "AB" and not (mark.isdigit() and 0 <= int(mark) <= subject["max_internal"]):
            problems.append(f"Row {n}: marks must be a whole number from 0 to {subject['max_internal']} or AB.")
    for prn in sorted(set(expected) - seen):
        problems.append(f"{prn} ({expected[prn]['name']}) is missing.")
    return {"ok": not problems, "rows": len(rows) - 1, "problems": problems[:200]}
