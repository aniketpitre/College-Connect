"""
Placement (spec §3.14, plan 3.8): company drives, eligibility rules, student registration with a
resume, round-by-round results, offers and statistics (for NAAC/NIRF).

Eligibility is checked from the student's own record: programme, year of study, and CGPA and
backlogs from published results (`results.standing`). A student registers for an open drive
before its last date with a resume on file; the Placement Officer moves registrants through the
drive's rounds and records offers.
"""

import csv
import io
import statistics
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock, files
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.modules.placement.schemas import DriveIn, ProfileIn
from app.modules.results import service as results
from app.modules.students import service as students

register_indexes("drives", [IndexModel([("status", ASCENDING), ("register_by", ASCENDING)])])
register_indexes(
    "drive_registrations",
    [
        IndexModel([("drive_id", ASCENDING), ("student_id", ASCENDING)], unique=True),
        IndexModel([("student_id", ASCENDING)]),
    ],
)
register_indexes("placement_profiles", [IndexModel([("student_id", ASCENDING)], unique=True)])

STATUS_LABELS = {
    "registered": "Registered",
    "in_process": "In process",
    "selected": "Selected",
    "rejected": "Not selected",
    "withdrawn": "Withdrawn",
}


def oid(value: Any, what: str) -> ObjectId:
    return students.oid(value, what)


# --- eligibility ----------------------------------------------------------------------------


def eligibility(
    student: dict[str, Any], drive: dict[str, Any], standing: dict[str, Any] | None = None
) -> dict[str, Any]:
    rules = drive["eligibility"]
    standing = standing or results.standing(student["_id"])
    reasons = []
    if rules.get("programme_ids") and student.get("programme_id") not in rules["programme_ids"]:
        reasons.append("programme")
    if rules.get("years") and student.get("year_of_study") not in rules["years"]:
        reasons.append("year")
    cgpa = standing.get("cgpa")
    if rules.get("min_cgpa") is not None and (cgpa is None or cgpa < rules["min_cgpa"]):
        reasons.append("cgpa")
    backlogs = len(standing.get("backlogs", []))
    if rules.get("max_backlogs") is not None and backlogs > rules["max_backlogs"]:
        reasons.append("backlogs")
    return {"eligible": not reasons, "reasons": reasons, "cgpa": cgpa, "backlogs": backlogs}


# --- drives (Placement Officer) -------------------------------------------------------------


def _drive_doc(body: DriveIn) -> dict[str, Any]:
    e = body.eligibility
    return {
        "company": body.company.strip(),
        "role": body.role.strip(),
        "ctc_lpa": body.ctc_lpa,
        "location": body.location.strip(),
        "description": body.description.strip(),
        "register_by": body.register_by.isoformat(),
        "drive_date": body.drive_date.isoformat() if body.drive_date else None,
        "rounds": [r.strip() for r in body.rounds if r.strip()],
        "eligibility": {
            "programme_ids": [oid(p, "Programme") for p in e.programme_ids],
            "years": e.years,
            "min_cgpa": e.min_cgpa,
            "max_backlogs": e.max_backlogs,
        },
        "status": body.status,
    }


def drive_view(d: dict[str, Any], *, counts: bool = False) -> dict[str, Any]:
    db = get_db()
    progs = {
        p["_id"]: p["code"]
        for p in db.programmes.find({"_id": {"$in": d["eligibility"]["programme_ids"]}}, {"code": 1})
    }
    out = {
        "id": str(d["_id"]),
        "company": d["company"],
        "role": d["role"],
        "ctc_lpa": d["ctc_lpa"],
        "location": d["location"],
        "description": d["description"],
        "register_by": d["register_by"],
        "drive_date": d.get("drive_date"),
        "rounds": d["rounds"],
        "status": d["status"],
        "open_now": d["status"] == "open" and clock.today().isoformat() <= d["register_by"],
        "eligibility": {
            "programme_ids": [str(p) for p in d["eligibility"]["programme_ids"]],
            "programmes": [progs.get(p, "?") for p in d["eligibility"]["programme_ids"]],
            "years": d["eligibility"]["years"],
            "min_cgpa": d["eligibility"]["min_cgpa"],
            "max_backlogs": d["eligibility"]["max_backlogs"],
        },
    }
    if counts:
        regs = list(db.drive_registrations.find({"drive_id": d["_id"]}, {"status": 1}))
        out["counts"] = {s: sum(1 for r in regs if r["status"] == s) for s in STATUS_LABELS}
    return out


def create_drive(ctx: AuthContext, body: DriveIn) -> dict[str, Any]:
    doc = {**_drive_doc(body), "created_at": datetime.now(UTC), "created_by": ctx.user_id}
    doc["_id"] = get_db().drives.insert_one(doc).inserted_id
    audit.record(
        "placement.drive_created", actor_id=ctx.user_id, details={"company": doc["company"], "role": doc["role"]}
    )
    return drive_view(doc, counts=True)


def get_drive(drive_id: Any) -> dict[str, Any]:
    d = get_db().drives.find_one({"_id": drive_id if isinstance(drive_id, ObjectId) else oid(drive_id, "Drive")})
    if not d:
        raise AppError(404, "Drive not found.")
    return d


def update_drive(ctx: AuthContext, drive_id: str, body: DriveIn) -> dict[str, Any]:
    d = get_drive(drive_id)
    get_db().drives.update_one({"_id": d["_id"]}, {"$set": _drive_doc(body)})
    audit.record(
        "placement.drive_updated", actor_id=ctx.user_id, details={"company": body.company, "status": body.status}
    )
    return drive_view(get_drive(d["_id"]), counts=True)


def list_drives() -> list[dict[str, Any]]:
    return [drive_view(d, counts=True) for d in get_db().drives.find({}).sort("register_by", DESCENDING).limit(200)]


def _round_label(drive: dict[str, Any], r: dict[str, Any]) -> str:
    if r["status"] == "selected":
        return "Selected"
    if r["status"] in ("rejected", "withdrawn"):
        return STATUS_LABELS[r["status"]]
    n = r.get("round", 0)
    return drive["rounds"][n - 1] if 0 < n <= len(drive["rounds"]) else "Registered"


def registrations(drive_id: str) -> dict[str, Any]:
    d = get_drive(drive_id)
    db = get_db()
    regs = list(db.drive_registrations.find({"drive_id": d["_id"]}).sort("created_at", ASCENDING))
    people = {s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in regs]}})}
    lookups = students._lookups()
    rows = []
    for r in regs:
        s = people.get(r["student_id"])
        if not s:
            continue
        summary = students.summary(s, lookups)
        rows.append(
            {
                "id": str(r["_id"]),
                "student_id": str(s["_id"]),
                "name": s["name"],
                "prn": s["prn"],
                "class": " ".join(
                    x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x
                ),
                "email": s.get("email"),
                "phone": s.get("phone"),
                "cgpa": r.get("cgpa"),
                "backlogs": r.get("backlogs"),
                "status": r["status"],
                "round": r.get("round", 0),
                "stage": _round_label(d, r),
                "offer_lpa": (r.get("offer") or {}).get("ctc_lpa"),
                "has_resume": bool(r.get("resume_file_id")),
            }
        )
    return {"drive": drive_view(d, counts=True), "registrations": rows}


def registrations_csv(drive_id: str) -> tuple[str, str]:
    data = registrations(drive_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["PRN", "Name", "Class", "Email", "Mobile", "CGPA", "Backlogs", "Stage"])
    for r in data["registrations"]:
        if r["status"] != "withdrawn":
            w.writerow(
                [
                    r["prn"],
                    r["name"],
                    r["class"],
                    r["email"] or "",
                    r["phone"] or "",
                    r["cgpa"] or "",
                    r["backlogs"],
                    r["stage"],
                ]
            )
    name = f"{data['drive']['company']}-{data['drive']['role']}".replace(" ", "_")[:60]
    return buf.getvalue(), f"{name}-registrations.csv"


def record_results(ctx: AuthContext, drive_id: str, ids: list[str], action: str, ctc: float | None) -> dict[str, Any]:
    from app.modules.messaging import service as messaging

    d = get_drive(drive_id)
    db = get_db()
    targets = list(
        db.drive_registrations.find(
            {
                "_id": {"$in": [oid(i, "Registration") for i in ids]},
                "drive_id": d["_id"],
                "status": {"$in": ["registered", "in_process"]},
            }
        )
    )
    if not targets:
        raise AppError(409, "None of these students are still in the drive.", "conflict")
    for r in targets:
        if action == "next":
            if r.get("round", 0) >= len(d["rounds"]):
                raise AppError(409, "These students have finished every round: select or reject them.", "last_round")
            update: dict[str, Any] = {"status": "in_process", "round": r.get("round", 0) + 1}
        elif action == "reject":
            update = {"status": "rejected"}
        else:
            update = {
                "status": "selected",
                "offer": {"ctc_lpa": ctc if ctc is not None else d["ctc_lpa"], "at": datetime.now(UTC)},
            }
        db.drive_registrations.update_one({"_id": r["_id"]}, {"$set": update})
        if action == "select":
            s = db.students.find_one({"_id": r["student_id"]})
            if s:
                messaging.notify(s, "placement_selected", {"company": d["company"], "role": d["role"]})
    audit.record(
        "placement.results",
        actor_id=ctx.user_id,
        details={"drive": d["company"], "action": action, "students": len(targets)},
    )
    return registrations(drive_id)


def resume_for(registration_id: str) -> dict[str, Any]:
    r = get_db().drive_registrations.find_one({"_id": oid(registration_id, "Registration")})
    if not r or not r.get("resume_file_id"):
        raise AppError(404, "No resume.")
    return files.load(str(r["resume_file_id"]))


# --- the student ----------------------------------------------------------------------------


def _profile(student_id: ObjectId) -> dict[str, Any]:
    return get_db().placement_profiles.find_one({"student_id": student_id}) or {}


def my_placement(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    db = get_db()
    standing = results.standing(student["_id"])
    prof = _profile(student["_id"])
    regs = {r["drive_id"]: r for r in db.drive_registrations.find({"student_id": student["_id"]})}
    drives = list(
        db.drives.find({"$or": [{"status": "open"}, {"_id": {"$in": list(regs)}}]}).sort("register_by", ASCENDING)
    )
    out = []
    for d in drives:
        r = regs.get(d["_id"])
        e = eligibility(student, d, standing)
        if not r and not e["eligible"] and d["status"] != "open":
            continue
        out.append(
            {
                **drive_view(d),
                "eligible": e["eligible"],
                "reasons": e["reasons"],
                "registration": {
                    "id": str(r["_id"]),
                    "status": r["status"],
                    "stage": _round_label(d, r),
                    "offer_lpa": (r.get("offer") or {}).get("ctc_lpa"),
                }
                if r
                else None,
            }
        )
    return {
        "profile": {
            "skills": prof.get("skills", ""),
            "linkedin": prof.get("linkedin", ""),
            "resume_name": prof.get("resume_name"),
            "resume_url": f"/files/{prof['resume_file_id']}" if prof.get("resume_file_id") else None,
        },
        "cgpa": standing.get("cgpa"),
        "backlogs": len(standing.get("backlogs", [])),
        "drives": out,
    }


def save_profile(ctx: AuthContext, body: ProfileIn) -> dict[str, Any]:
    student = students.my_student(ctx)
    get_db().placement_profiles.update_one(
        {"student_id": student["_id"]},
        {"$set": {"skills": body.skills.strip(), "linkedin": body.linkedin.strip(), "updated_at": datetime.now(UTC)}},
        upsert=True,
    )
    return my_placement(ctx)


def upload_resume(ctx: AuthContext, filename: str, data: bytes) -> dict[str, Any]:
    student = students.my_student(ctx)
    saved = files.save(data, filename=filename, student_id=student["_id"], purpose="resume", created_by=ctx.user_id)
    if saved["content_type"] != "application/pdf":
        get_db().files.delete_one({"_id": saved["_id"]})
        raise AppError(415, "Upload your resume as a PDF.", "unsupported_file", "file")
    db = get_db()
    old = _profile(student["_id"]).get("resume_file_id")
    db.placement_profiles.update_one(
        {"student_id": student["_id"]},
        {"$set": {"resume_file_id": saved["_id"], "resume_name": saved["filename"], "updated_at": datetime.now(UTC)}},
        upsert=True,
    )
    if old and not db.drive_registrations.find_one({"resume_file_id": old}):
        db.files.delete_one({"_id": old})  # keep a resume a company already received
    return my_placement(ctx)


def register(ctx: AuthContext, drive_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    d = get_drive(drive_id)
    if d["status"] != "open" or clock.today().isoformat() > d["register_by"]:
        raise AppError(409, "Registration for this drive is closed.", "closed")
    standing = results.standing(student["_id"])
    e = eligibility(student, d, standing)
    if not e["eligible"]:
        raise AppError(409, "You don't meet this drive's eligibility rules.", "not_eligible")
    prof = _profile(student["_id"])
    if not prof.get("resume_file_id"):
        raise AppError(409, "Upload your resume first.", "no_resume")
    db = get_db()
    existing = db.drive_registrations.find_one({"drive_id": d["_id"], "student_id": student["_id"]})
    if existing and existing["status"] == "withdrawn":
        db.drive_registrations.update_one(
            {"_id": existing["_id"]},
            {"$set": {"status": "registered", "round": 0, "resume_file_id": prof["resume_file_id"]}},
        )
    else:
        try:
            db.drive_registrations.insert_one(
                {
                    "drive_id": d["_id"],
                    "student_id": student["_id"],
                    "status": "registered",
                    "round": 0,
                    "cgpa": e["cgpa"],
                    "backlogs": e["backlogs"],
                    "resume_file_id": prof["resume_file_id"],
                    "created_at": datetime.now(UTC),
                }
            )
        except DuplicateKeyError as err:
            raise AppError(409, "You have already registered.", "conflict") from err
    return my_placement(ctx)


def withdraw(ctx: AuthContext, drive_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    d = get_drive(drive_id)
    res = get_db().drive_registrations.update_one(
        {"drive_id": d["_id"], "student_id": student["_id"], "status": "registered"}, {"$set": {"status": "withdrawn"}}
    )
    if not res.modified_count:
        raise AppError(409, "You can withdraw only before the first round.", "conflict")
    return my_placement(ctx)


# --- statistics -----------------------------------------------------------------------------


def stats() -> dict[str, Any]:
    """Offers and packages (NAAC criterion 5.2 / NIRF graduation outcomes)."""
    db = get_db()
    selected = list(db.drive_registrations.find({"status": "selected"}))
    drives = {d["_id"]: d for d in db.drives.find({}, {"company": 1, "ctc_lpa": 1})}
    packages = [
        (r.get("offer") or {}).get("ctc_lpa") or drives.get(r["drive_id"], {}).get("ctc_lpa", 0) for r in selected
    ]
    placed = {r["student_id"] for r in selected}
    people = {s["_id"]: s for s in db.students.find({"_id": {"$in": list(placed)}}, {"programme_id": 1})}
    progs = {p["_id"]: p["code"] for p in db.programmes.find({}, {"code": 1})}
    by_programme: dict[str, int] = {}
    for sid in placed:
        code = progs.get(people.get(sid, {}).get("programme_id"), "?")
        by_programme[code] = by_programme.get(code, 0) + 1
    return {
        "drives": len(drives),
        "companies": len({d["company"] for d in drives.values()}),
        "offers": len(selected),
        "students_placed": len(placed),
        "registered_students": len(db.drive_registrations.distinct("student_id")),
        "highest_lpa": max(packages) if packages else None,
        "average_lpa": round(statistics.mean(packages), 2) if packages else None,
        "median_lpa": round(statistics.median(packages), 2) if packages else None,
        "by_programme": by_programme,
    }
