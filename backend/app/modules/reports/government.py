"""
Government reporting (plan 4.2): the AISHE data sheet, NIRF data points, and APAAR / ABC IDs.

AISHE counts students by programme, year, gender and social group, and staff by designation,
gender and social group. NIRF asks for intake, strength, outcomes and faculty figures. APAAR
(the student's Academic Bank of Credits ID, 12 digits) is checked for missing, malformed and
duplicate IDs, can be imported from the CSV the ABC portal gives, and credits earned are
exported in a CSV for upload to the ABC portal.
"""

import csv
import io
import re
from collections import Counter
from statistics import median
from typing import Any

from bson import ObjectId

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.modules.reports import common

APAAR = re.compile(r"^\d{12}$")
GENDERS = ("female", "male", "other")


def _blank_counts() -> dict[str, int]:
    out = {"total": 0, **{g: 0 for g in GENDERS}, **{g: 0 for g in common.GROUP_LABELS}}
    return out


def aishe(year_id: str | None) -> dict[str, Any]:
    y = common.year(year_id)
    progs = common.programmes()
    groups = common.category_groups()
    rows: dict[tuple[ObjectId, int], dict[str, Any]] = {}
    no_gender = no_category = 0
    for s in common.active_students({"programme_id": 1, "year_of_study": 1, "gender": 1, "category_id": 1}):
        p = progs.get(s.get("programme_id"))  # type: ignore[arg-type]
        if not p:
            continue
        key = (p["_id"], s.get("year_of_study", 1))
        row = rows.setdefault(key, {"programme": p["code"], "year": s.get("year_of_study", 1), **_blank_counts()})
        row["total"] += 1
        if s.get("gender") in GENDERS:
            row[s["gender"]] += 1
        else:
            no_gender += 1
        group = groups.get(s.get("category_id"))  # type: ignore[arg-type]
        if group:
            row[group] += 1
        else:
            no_category += 1
    students = sorted(rows.values(), key=lambda r: (r["programme"], r["year"]))

    teachers, missing = common.teachers()
    staff_rows: dict[tuple[str, str], dict[str, Any]] = {}
    staff_no_gender = 0
    db = get_db()
    non_teaching = list(db.staff_profiles.find({"teaching": False, "left_on": None}))
    for p, kind in [*((t, "Teaching") for t in teachers), *((n, "Non-teaching") for n in non_teaching)]:
        key = (kind, p.get("designation") or "—")
        row = staff_rows.setdefault(key, {"staff": kind, "designation": key[1], **_blank_counts()})
        row["total"] += 1
        if p.get("gender") in GENDERS:
            row[p["gender"]] += 1
        else:
            staff_no_gender += 1
        if p.get("social_category"):
            row[p["social_category"]] += 1
    staff = sorted(staff_rows.values(), key=lambda r: (r["staff"], r["designation"]))

    gaps = []
    if no_gender:
        gaps.append(f"{no_gender} student(s) have no gender recorded.")
    if no_category:
        gaps.append(f"{no_category} student(s) have no category recorded.")
    if staff_no_gender:
        gaps.append(f"{staff_no_gender} staff record(s) have no gender recorded.")
    if missing:
        gaps.append(f"{missing} teaching account(s) have no staff record.")
    gaps.append(
        "Persons with disability and minority status are not recorded in CollegeConnect yet: "
        "fill them in on the portal."
    )
    return {"year": y["name"], "students": students, "staff": staff, "gaps": gaps}


AISHE_COLUMNS = [
    ("total", "Total"),
    ("female", "Female"),
    ("male", "Male"),
    ("other", "Transgender"),
    ("general", "General"),
    ("ews", "EWS"),
    ("sc", "SC"),
    ("st", "ST"),
    ("obc", "OBC"),
]


def aishe_csv(year_id: str | None, part: str) -> tuple[str, str]:
    data = aishe(year_id)
    if part == "staff":
        cols = [("staff", "Staff"), ("designation", "Designation"), *AISHE_COLUMNS]
        return common.to_csv(cols, data["staff"]), f"aishe-staff-{data['year']}.csv"
    cols = [("programme", "Programme"), ("year", "Year"), *AISHE_COLUMNS]
    return common.to_csv(cols, data["students"]), f"aishe-students-{data['year']}.csv"


def nirf(year_id: str | None) -> dict[str, Any]:
    """The NIRF data points CollegeConnect can fill (the rest are entered on the portal)."""
    from app.modules.reports import naac

    y = common.year(year_id)
    db = get_db()
    progs = common.programmes()
    students = common.active_students(
        {"gender": 1, "address": 1, "category_id": 1, "programme_id": 1, "year_of_study": 1}
    )
    groups = common.category_groups()
    seats = naac.cycle_seats(y)
    manual = naac.settings()["intake"]
    intake = sum((seats[p]["seats"] if p in seats else manual.get(str(p), 0)) or 0 for p in progs)
    state = Counter((s.get("address") or {}).get("state") or "Maharashtra" for s in students)
    teachers, _ = common.teachers()
    exp = [t.get("experience_years", 0) for t in teachers]
    first, last = common.span(y)
    drives = {d["_id"]: d for d in db.drives.find({"created_at": {"$gte": first, "$lt": last}}, {"ctc_lpa": 1})}
    selected = list(
        db.drive_registrations.find(
            {"drive_id": {"$in": list(drives)}, "status": "selected"}, {"drive_id": 1, "student_id": 1}
        )
    )
    ctcs = [drives[s["drive_id"]]["ctc_lpa"] for s in selected if drives[s["drive_id"]].get("ctc_lpa")]
    passed = naac.pass_percentage(y)["rows"]
    points = [
        ("Sanctioned intake (first year)", intake),
        ("Total students", len(students)),
        ("Female students", sum(1 for s in students if s.get("gender") == "female")),
        ("Students from within the state", state.get("Maharashtra", 0)),
        ("Students from other states", len(students) - state.get("Maharashtra", 0)),
        (
            "Socially challenged students (SC, ST, OBC)",
            sum(1 for s in students if groups.get(s.get("category_id") or ObjectId()) in {"sc", "st", "obc"}),
        ),
        (
            "Students receiving full fee reimbursement / scholarship",
            db.scholarships.count_documents(
                {"academic_year_id": y["_id"], "status": {"$in": ["sanctioned", "received"]}}
            ),
        ),
        ("Final-year students who passed", sum(r["passed"] for r in passed)),
        ("Students placed", len({s["student_id"] for s in selected})),
        ("Median salary of placed students (Rs. lakh a year)", median(ctcs) if ctcs else None),
        ("Full-time teachers", sum(1 for t in teachers if t.get("employment") == "permanent")),
        (
            "Teachers with Ph.D.",
            sum(1 for t in teachers if any(q["level"] == "phd" for q in t.get("qualifications", []))),
        ),
        ("Average teaching experience before joining (years)", round(sum(exp) / len(exp), 1) if exp else None),
    ]
    return {"year": y["name"], "points": [{"item": k, "value": v} for k, v in points]}


def nirf_csv(year_id: str | None) -> tuple[str, str]:
    data = nirf(year_id)
    return common.to_csv([("item", "Data point"), ("value", "Value")], data["points"]), f"nirf-{data['year']}.csv"


# --- APAAR / ABC ----------------------------------------------------------------------------


def _valid(apaar: str) -> bool:
    return bool(APAAR.match(apaar)) and len(set(apaar)) > 1


def apaar_check() -> dict[str, Any]:
    students = common.active_students({"name": 1, "prn": 1, "apaar_id": 1, "year_of_study": 1})
    ids = Counter(s["apaar_id"] for s in students if s.get("apaar_id"))
    missing, invalid, duplicate = [], [], []
    for s in sorted(students, key=lambda s: s.get("prn") or ""):
        brief = {"id": str(s["_id"]), "prn": s.get("prn"), "name": s["name"], "apaar_id": s.get("apaar_id")}
        if not s.get("apaar_id"):
            missing.append(brief)
        elif not _valid(s["apaar_id"]):
            invalid.append(brief)
        elif ids[s["apaar_id"]] > 1:
            duplicate.append(brief)
    ok = len(students) - len(missing) - len(invalid) - len(duplicate)
    return {"students": len(students), "valid": ok, "missing": missing, "invalid": invalid, "duplicate": duplicate}


def import_apaar(ctx: AuthContext, data: bytes, ip: str) -> dict[str, Any]:
    """A CSV with PRN and APAAR ID columns (the ABC portal's download, or one kept by the office)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AppError(422, "Upload the CSV file saved as UTF-8.", field="file") from e
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower().replace(" ", "_"): f for f in reader.fieldnames or []}
    prn_col = next((fields[k] for k in ("prn", "registration_no", "enrolment_no") if k in fields), None)
    id_col = next((fields[k] for k in ("apaar_id", "apaar", "abc_id", "abc") if k in fields), None)
    if not prn_col or not id_col:
        raise AppError(422, "The CSV needs a PRN column and an APAAR ID column.", field="file")
    db = get_db()
    updated, problems = 0, []
    for n, row in enumerate(reader, start=2):
        prn = (row.get(prn_col) or "").strip().upper()
        apaar = re.sub(r"\D", "", row.get(id_col) or "")
        if not prn:
            continue
        if not _valid(apaar):
            problems.append({"row": n, "prn": prn, "problem": "The APAAR ID must be 12 digits."})
            continue
        other = db.students.find_one({"apaar_id": apaar, "prn": {"$ne": prn}}, {"prn": 1})
        if other:
            problems.append({"row": n, "prn": prn, "problem": f"This APAAR ID already belongs to {other['prn']}."})
            continue
        r = db.students.update_one({"prn": prn}, {"$set": {"apaar_id": apaar}})
        if not r.matched_count:
            problems.append({"row": n, "prn": prn, "problem": "No student with this PRN."})
        updated += r.modified_count
    audit.record(
        "students.apaar_imported", actor_id=ctx.user_id, ip=ip, details={"updated": updated, "problems": len(problems)}
    )
    return {
        "updated": updated,
        "problems": problems[:200],
        **{k: v for k, v in apaar_check().items() if k in ("students", "valid")},
    }


CREDIT_COLUMNS = [
    ("apaar_id", "APAAR ID"),
    ("prn", "PRN"),
    ("name", "Name"),
    ("programme", "Programme"),
    ("semester", "Semester"),
    ("course_code", "Course code"),
    ("course_name", "Course name"),
    ("credits", "Credits earned"),
    ("grade", "Grade"),
    ("grade_point", "Grade point"),
    ("exam", "Exam"),
]


def credit_rows(year_id: str | None) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """Credits earned in the year's published results, one row per course passed, for the ABC
    portal. Students without a valid APAAR ID are left out and counted."""
    y = common.year(year_id)
    db = get_db()
    sessions = {
        s["_id"]: s
        for s in db.exam_sessions.find({"academic_year_id": y["_id"], "results_published": True}, {"name": 1})
    }
    results = list(db.results.find({"session_id": {"$in": list(sessions)}}))
    people = {
        s["_id"]: s
        for s in db.students.find(
            {"_id": {"$in": list({r["student_id"] for r in results})}},
            {"name": 1, "prn": 1, "apaar_id": 1, "programme_id": 1},
        )
    }
    progs = common.programmes()
    rows, skipped = [], set()
    for r in results:
        s = people.get(r["student_id"])
        if not s:
            continue
        if not (s.get("apaar_id") and _valid(s["apaar_id"])):
            skipped.add(s["_id"])
            continue
        for sub in r.get("subjects", []):
            if not sub.get("passed"):
                continue
            rows.append(
                {
                    "apaar_id": s["apaar_id"],
                    "prn": s.get("prn"),
                    "name": s["name"],
                    "programme": progs.get(s.get("programme_id"), {}).get("code"),  # type: ignore[arg-type]
                    "semester": sub.get("semester"),
                    "course_code": sub.get("code"),
                    "course_name": sub.get("name"),
                    "credits": sub.get("credits"),
                    "grade": sub.get("grade"),
                    "grade_point": sub.get("grade_point"),
                    "exam": sessions[r["session_id"]]["name"],
                }
            )
    rows.sort(key=lambda x: (x["prn"] or "", x["semester"] or 0, x["course_code"] or ""))
    return y, rows, len(skipped)


def credits_preview(year_id: str | None) -> dict[str, Any]:
    y, rows, skipped = credit_rows(year_id)
    return {
        "year": y["name"],
        "rows": len(rows),
        "students": len({r["prn"] for r in rows}),
        "credits": sum(r["credits"] or 0 for r in rows),
        "skipped_without_apaar": skipped,
        "sample": rows[:10],
    }


def credits_csv(ctx: AuthContext, year_id: str | None) -> tuple[str, str]:
    y, rows, skipped = credit_rows(year_id)
    audit.record(
        "reports.abc_credits_exported",
        actor_id=ctx.user_id,
        details={"year": y["name"], "rows": len(rows), "skipped": skipped},
    )
    return common.to_csv(CREDIT_COLUMNS, rows), f"abc-credits-{y['name']}.csv"
