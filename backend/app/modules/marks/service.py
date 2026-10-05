"""
Internal marks (spec §3.8, plan 2.5).

- An assessment scheme per subject and academic year lists the components (unit tests,
  assignment, practical…) whose maximums add up to the subject's internal maximum. The Exam Cell
  (any subject) or the HOD (own department) sets it, and the Exam Cell sets the deadline.
- One marks sheet per class and subject (`marks_sheets`): {student: {component: mark | "AB"}}.
  draft → published (students see it; the teacher can still correct) → approved (HOD) →
  locked (Exam Cell). The HOD can return a sheet to the teacher; the Exam Cell can unlock with
  a reason. After the deadline teachers can't change marks.
- Teachers of a subject are the teachers in the class's timetable for that subject.
"""

import math
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.marks.schemas import SchemeIn, SheetAction, SheetSave
from app.modules.setup import service as setup
from app.modules.timetable import service as timetable

register_indexes(
    "assessment_schemes", [IndexModel([("subject_id", ASCENDING), ("academic_year_id", ASCENDING)], unique=True)]
)
register_indexes(
    "marks_sheets",
    [
        IndexModel([("scheme_id", ASCENDING), ("division_id", ASCENDING)], unique=True),
        IndexModel([("academic_year_id", ASCENDING), ("status", ASCENDING)]),
    ],
)

STATUS_LABELS = {
    "draft": "Draft",
    "published": "Published to students",
    "approved": "Approved by HOD",
    "locked": "Locked",
}
VISIBLE_TO_STUDENTS = {"published", "approved", "locked"}


def _oid(value: Any, what: str, field: str | None = None) -> ObjectId:
    return timetable.oid(value, what, field)


def current_year_id(academic_year_id: str | None = None) -> ObjectId:
    if academic_year_id:
        return _oid(academic_year_id, "Academic year", "academic_year_id")
    year = setup.current_year()
    if not year:
        raise AppError(409, "Set the current academic year in College setup first.", "no_current_year")
    return year["_id"]


def _subject(subject_id: Any) -> dict[str, Any]:
    subject = get_db().subjects.find_one(
        {"_id": subject_id if isinstance(subject_id, ObjectId) else _oid(subject_id, "Subject", "subject_id")}
    )
    if not subject:
        raise AppError(422, "Subject not found.", field="subject_id")
    return subject


def _department_of_subject(subject: dict[str, Any]) -> ObjectId | None:
    programme = get_db().programmes.find_one({"_id": subject["programme_id"]}, {"department_id": 1})
    return programme.get("department_id") if programme else None


def can_manage_scheme(ctx: AuthContext, subject: dict[str, Any]) -> bool:
    if P.EXAMS_MANAGE in ctx.permissions:
        return True
    dept = ctx.user.get("department_id")
    return P.MARKS_SCHEME_DEPT in ctx.permissions and dept is not None and _department_of_subject(subject) == dept


def teaches(ctx: AuthContext, division_id: ObjectId, subject_id: ObjectId) -> bool:
    return P.MARKS_ENTER in ctx.permissions and bool(
        get_db().timetable_slots.find_one(
            {"division_id": division_id, "subject_id": subject_id, "faculty_ids": ctx.user_id}, {"_id": 1}
        )
    )


def is_hod_for(ctx: AuthContext, division: dict[str, Any]) -> bool:
    dept = ctx.user.get("department_id")
    return P.MARKS_APPROVE in ctx.permissions and dept is not None and timetable.department_of(division) == dept


def can_read(ctx: AuthContext, division: dict[str, Any], subject_id: ObjectId) -> bool:
    return (
        P.MARKS_READ in ctx.permissions
        or P.EXAMS_MANAGE in ctx.permissions
        or is_hod_for(ctx, division)
        or teaches(ctx, division["_id"], subject_id)
    )


# --- schemes --------------------------------------------------------------------------------


def scheme_view(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(s["_id"]),
        "subject_id": str(s["subject_id"]),
        "academic_year_id": str(s["academic_year_id"]),
        "components": [{**c, "held_on": c.get("held_on")} for c in s["components"]],
        "total": s["total"],
        "deadline": s.get("deadline"),
        "locked_in": bool(s.get("in_use")),
    }


def save_scheme(ctx: AuthContext, body: SchemeIn, ip: str) -> dict[str, Any]:
    subject = _subject(body.subject_id)
    if not can_manage_scheme(ctx, subject):
        raise AppError(403, "You can only set schemes for your own department.", "forbidden")
    year_id = current_year_id(body.academic_year_id)
    db = get_db()
    existing = db.assessment_schemes.find_one({"subject_id": subject["_id"], "academic_year_id": year_id})
    deadline_changed = body.deadline is not None and (
        not existing or existing.get("deadline") != body.deadline.isoformat()
    )
    if deadline_changed and P.EXAMS_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell sets the marks deadline.", "forbidden", "deadline")
    old_keys = {c["key"] for c in (existing or {}).get("components", [])}
    used: set[str] = set()
    next_n = 1 + max((int(k[1:]) for k in old_keys if k[1:].isdigit()), default=0)
    components: list[dict[str, Any]] = []
    for c in body.components:
        if c.key and c.key in old_keys and c.key not in used:
            key: str = c.key
        else:  # a new component gets a key never used before, so old marks can't attach to it
            key, next_n = f"c{next_n}", next_n + 1
        used.add(key)
        components.append(
            {"key": key, "name": c.name.strip(), "max": c.max, "held_on": c.held_on.isoformat() if c.held_on else None}
        )
    total = round(sum(c["max"] for c in components), 2)
    if total != subject["max_internal"]:
        raise AppError(
            422,
            f"The components add up to {total:g}; {subject['code']} has {subject['max_internal']} internal marks.",
            field="components",
        )
    if existing and existing.get("in_use"):
        removed = old_keys - {c["key"] for c in components}
        changed_max = {
            c["key"]
            for c in components
            if any(o["key"] == c["key"] and o["max"] != c["max"] for o in existing["components"])
        }
        if removed or changed_max:
            approved = db.marks_sheets.count_documents(
                {"scheme_id": existing["_id"], "status": {"$in": ["approved", "locked"]}}
            )
            if approved:
                raise AppError(
                    409, "Marks were already approved under this scheme; only names and dates can change.", "conflict"
                )
    doc = {
        "subject_id": subject["_id"],
        "academic_year_id": year_id,
        "components": components,
        "total": total,
        "deadline": body.deadline.isoformat() if body.deadline else (existing or {}).get("deadline"),
        "updated_by": ctx.user_id,
        "updated_at": clock.now(),
    }
    if existing:
        db.assessment_schemes.update_one({"_id": existing["_id"]}, {"$set": doc})
        doc = {**existing, **doc}
    else:
        try:
            doc["_id"] = db.assessment_schemes.insert_one({**doc, "created_at": clock.now()}).inserted_id
        except DuplicateKeyError as e:
            raise AppError(409, "Someone else just set this scheme. Reload.", "conflict") from e
    audit.record(
        "marks.scheme_saved",
        actor_id=ctx.user_id,
        target_type="subject",
        target_id=subject["_id"],
        ip=ip,
        details={
            "subject": subject["code"],
            "components": [f"{c['name']} /{c['max']:g}" for c in components],
            "deadline": doc["deadline"],
        },
    )
    return scheme_view(doc)


def list_schemes(
    ctx: AuthContext, programme_id: str, semester: int | None, academic_year_id: str | None
) -> list[dict[str, Any]]:
    db = get_db()
    year_id = current_year_id(academic_year_id)
    query: dict[str, Any] = {
        "programme_id": _oid(programme_id, "Programme", "programme_id"),
        "status": {"$ne": "archived"},
    }
    if semester:
        query["semester"] = semester
    subjects = list(db.subjects.find(query).sort([("semester", ASCENDING), ("code", ASCENDING)]))
    schemes = {
        s["subject_id"]: s
        for s in db.assessment_schemes.find(
            {"subject_id": {"$in": [s["_id"] for s in subjects]}, "academic_year_id": year_id}
        )
    }
    return [
        {
            "subject_id": str(s["_id"]),
            "code": s["code"],
            "name": s["name"],
            "semester": s["semester"],
            "max_internal": s["max_internal"],
            "scheme": scheme_view(schemes[s["_id"]]) if s["_id"] in schemes else None,
            "can_manage": can_manage_scheme(ctx, s),
        }
        for s in subjects
    ]


# --- sheets ---------------------------------------------------------------------------------


def _scheme_for(subject_id: ObjectId, year_id: ObjectId) -> dict[str, Any]:
    scheme = get_db().assessment_schemes.find_one({"subject_id": subject_id, "academic_year_id": year_id})
    if not scheme:
        raise AppError(
            409, "The assessment scheme for this subject isn't set yet. Ask your HOD or the Exam Cell.", "no_scheme"
        )
    return scheme


def class_students(division_id: ObjectId) -> list[dict[str, Any]]:
    from app.modules.attendance.service import _roll_key

    rows = list(
        get_db().students.find({"division_id": division_id, "status": "active"}, {"name": 1, "prn": 1, "roll_no": 1})
    )
    return sorted(rows, key=_roll_key)


def deadline_passed(scheme: dict[str, Any]) -> bool:
    return bool(scheme.get("deadline")) and clock.today().isoformat() > scheme["deadline"]


def _flags(
    ctx: AuthContext, sheet: dict[str, Any] | None, scheme: dict[str, Any], division: dict[str, Any]
) -> dict[str, bool]:
    status = sheet["status"] if sheet else "draft"
    teacher = teaches(ctx, division["_id"], scheme["subject_id"])
    hod = is_hod_for(ctx, division)
    exam = P.EXAMS_MANAGE in ctx.permissions
    open_for_teacher = status in ("draft", "published") and not deadline_passed(scheme)
    return {
        "can_edit": teacher and open_for_teacher,
        "can_publish": teacher and status == "draft" and not deadline_passed(scheme) and bool(sheet),
        "can_approve": hod and status == "published",
        "can_return": hod and status in ("published", "approved"),
        "can_lock": exam and status in ("published", "approved"),
        "can_unlock": exam and status == "locked",
    }


def total_of(entry: dict[str, Any], scheme: dict[str, Any]) -> float | None:
    """Sum of the components; None while any component is missing. "AB" counts as 0."""
    total = 0.0
    for c in scheme["components"]:
        v = entry.get(c["key"])
        if v is None:
            return None
        total += 0 if v == "AB" else float(v)
    return round(total, 2)


def sheet(ctx: AuthContext, division_id: str, subject_id: str) -> dict[str, Any]:
    db = get_db()
    division = db.divisions.find_one({"_id": _oid(division_id, "Class", "division_id")})
    if not division:
        raise AppError(422, "Class not found.", field="division_id")
    subject = _subject(subject_id)
    if not can_read(ctx, division, subject["_id"]):
        raise AppError(403, "You don't teach this subject in this class.", "forbidden")
    scheme = _scheme_for(subject["_id"], current_year_id())
    doc = db.marks_sheets.find_one({"scheme_id": scheme["_id"], "division_id": division["_id"]})
    students = class_students(division["_id"])
    marks = (doc or {}).get("marks", {})
    names = {
        u["_id"]: u["name"]
        for u in db.users.find(
            {
                "_id": {
                    "$in": [
                        x
                        for x in [
                            (doc or {}).get("updated_by"),
                            (doc or {}).get("approved_by"),
                            (doc or {}).get("locked_by"),
                        ]
                        if x
                    ]
                }
            },
            {"name": 1},
        )
    }
    return {
        "class": timetable._division_label(division),
        "division_id": str(division["_id"]),
        "subject": {
            "id": str(subject["_id"]),
            "code": subject["code"],
            "name": subject["name"],
            "max_internal": subject["max_internal"],
        },
        "scheme": scheme_view(scheme),
        "status": doc["status"] if doc else "draft",
        "status_label": STATUS_LABELS[doc["status"] if doc else "draft"],
        "version": doc["version"] if doc else 0,
        "returned_reason": (doc or {}).get("returned_reason"),
        "saved_by": names.get((doc or {}).get("updated_by")),
        "approved_by": names.get((doc or {}).get("approved_by")),
        "locked_by": names.get((doc or {}).get("locked_by")),
        "deadline_passed": deadline_passed(scheme),
        "students": [
            {
                "id": str(s["_id"]),
                "name": s["name"],
                "prn": s["prn"],
                "roll_no": s.get("roll_no"),
                "marks": marks.get(str(s["_id"]), {}),
                "total": total_of(marks.get(str(s["_id"]), {}), scheme),
            }
            for s in students
        ],
        **_flags(ctx, doc, scheme, division),
    }


def _clean(value: Any, component: dict[str, Any], who: str) -> float | str | None:
    if value is None or value == "":
        return None
    if value == "AB":
        return "AB"
    v = float(value)
    if v < 0 or v > component["max"]:
        raise AppError(422, f"{who}: {component['name']} must be between 0 and {component['max']:g}.", field="marks")
    if round(v * 2) != v * 2:
        raise AppError(422, f"{who}: use whole or half marks.", field="marks")
    return v


def save(ctx: AuthContext, body: SheetSave, ip: str) -> dict[str, Any]:
    db = get_db()
    division = db.divisions.find_one({"_id": _oid(body.division_id, "Class", "division_id")})
    if not division:
        raise AppError(422, "Class not found.", field="division_id")
    subject = _subject(body.subject_id)
    if not teaches(ctx, division["_id"], subject["_id"]):
        raise AppError(403, "You don't teach this subject in this class.", "forbidden")
    year_id = current_year_id()
    scheme = _scheme_for(subject["_id"], year_id)
    doc = db.marks_sheets.find_one({"scheme_id": scheme["_id"], "division_id": division["_id"]})
    if not _flags(ctx, doc, scheme, division)["can_edit"]:
        if deadline_passed(scheme):
            raise AppError(403, "The deadline for these marks has passed. Ask the Exam Cell.", "deadline_passed")
        raise AppError(409, "These marks are approved or locked and can't be changed.", "not_editable")
    if (doc["version"] if doc else 0) != body.base_version:
        raise AppError(409, "Someone else saved these marks in the meantime. Reload first.", "marks_conflict")
    students = {str(s["_id"]): s for s in class_students(division["_id"])}
    components = {c["key"]: c for c in scheme["components"]}
    marks: dict[str, dict[str, Any]] = dict((doc or {}).get("marks", {}))
    for sid, entry in body.marks.items():
        if sid not in students:
            raise AppError(422, "A student in the marks isn't in this class.", field="marks")
        cleaned = dict(marks.get(sid, {}))
        for key, value in entry.items():
            if key not in components:
                raise AppError(422, "Unknown assessment component.", field="marks")
            cleaned[key] = _clean(value, components[key], students[sid]["name"])
        marks[sid] = {k: v for k, v in cleaned.items() if v is not None}
    now = clock.now()
    if doc:
        updated = db.marks_sheets.find_one_and_update(
            {"_id": doc["_id"], "version": doc["version"]},
            {
                "$set": {"marks": marks, "version": doc["version"] + 1, "updated_by": ctx.user_id, "updated_at": now},
                "$push": {"history": {"$each": [{"at": now, "by": ctx.user_id, "action": "saved"}], "$slice": -50}},
            },
            return_document=True,
        )
        if not updated:
            raise AppError(409, "Someone else saved these marks in the meantime. Reload first.", "marks_conflict")
    else:
        new = {
            "scheme_id": scheme["_id"],
            "subject_id": subject["_id"],
            "division_id": division["_id"],
            "academic_year_id": year_id,
            "status": "draft",
            "marks": marks,
            "version": 1,
            "created_at": now,
            "updated_by": ctx.user_id,
            "updated_at": now,
            "history": [{"at": now, "by": ctx.user_id, "action": "saved"}],
        }
        try:
            db.marks_sheets.insert_one(new)
        except DuplicateKeyError as e:
            raise AppError(
                409, "Someone else saved these marks in the meantime. Reload first.", "marks_conflict"
            ) from e
        db.assessment_schemes.update_one({"_id": scheme["_id"]}, {"$set": {"in_use": True}})
    audit.record(
        "marks.saved",
        actor_id=ctx.user_id,
        target_type="marks_sheet",
        target_id=f"{scheme['_id']}:{division['_id']}",
        ip=ip,
        details={"subject": subject["code"], "class": timetable._division_label(division), "students": len(body.marks)},
    )
    return sheet(ctx, body.division_id, body.subject_id)


TRANSITIONS = {
    "publish": ("can_publish", "published"),
    "approve": ("can_approve", "approved"),
    "return": ("can_return", "draft"),
    "lock": ("can_lock", "locked"),
    "unlock": ("can_unlock", "approved"),
}


def act(ctx: AuthContext, body: SheetAction, ip: str) -> dict[str, Any]:
    db = get_db()
    division = db.divisions.find_one({"_id": _oid(body.division_id, "Class", "division_id")})
    if not division:
        raise AppError(422, "Class not found.", field="division_id")
    subject = _subject(body.subject_id)
    scheme = _scheme_for(subject["_id"], current_year_id())
    doc = db.marks_sheets.find_one({"scheme_id": scheme["_id"], "division_id": division["_id"]})
    flag, new_status = TRANSITIONS[body.action]
    if not doc or not _flags(ctx, doc, scheme, division)[flag]:
        raise AppError(403, "You can't do that to these marks now.", "forbidden")
    if body.action in ("return", "unlock") and not (body.reason and body.reason.strip()):
        raise AppError(422, "Give a reason.", field="reason")
    now = clock.now()
    changes: dict[str, Any] = {"status": new_status}
    if body.action == "publish":
        changes.update({"published_at": now, "returned_reason": None})
    elif body.action == "approve":
        changes.update({"approved_by": ctx.user_id, "approved_at": now})
    elif body.action == "return":
        changes.update({"returned_reason": body.reason, "approved_by": None})
    elif body.action == "lock":
        changes.update({"locked_by": ctx.user_id, "locked_at": now})
    else:
        changes.update({"locked_by": None})
    updated = db.marks_sheets.update_one(
        {"_id": doc["_id"], "status": doc["status"]},
        {
            "$set": changes,
            "$push": {
                "history": {
                    "$each": [{"at": now, "by": ctx.user_id, "action": body.action, "reason": body.reason}],
                    "$slice": -50,
                }
            },
        },
    )
    if not updated.modified_count:
        raise AppError(409, "These marks changed in the meantime. Reload.", "conflict")
    audit.record(
        f"marks.{body.action}",
        actor_id=ctx.user_id,
        target_type="marks_sheet",
        target_id=str(doc["_id"]),
        ip=ip,
        reason=body.reason,
        details={"subject": subject["code"], "class": timetable._division_label(division)},
    )
    return sheet(ctx, body.division_id, body.subject_id)


# --- lists ----------------------------------------------------------------------------------


def _pairs_for(query: dict[str, Any]) -> set[tuple[ObjectId, ObjectId]]:
    year_id = current_year_id()
    pairs = set()
    for s in get_db().timetable_slots.find({**query, "academic_year_id": year_id}, {"division_id": 1, "subject_id": 1}):
        pairs.add((s["division_id"], s["subject_id"]))
    return pairs


def _rows(ctx: AuthContext, pairs: set[tuple[ObjectId, ObjectId]]) -> list[dict[str, Any]]:
    db = get_db()
    year_id = current_year_id()
    subjects = {s["_id"]: s for s in db.subjects.find({"_id": {"$in": list({p[1] for p in pairs})}})}
    divisions = {d["_id"]: d for d in db.divisions.find({"_id": {"$in": list({p[0] for p in pairs})}})}
    schemes = {
        s["subject_id"]: s
        for s in db.assessment_schemes.find({"subject_id": {"$in": list(subjects)}, "academic_year_id": year_id})
    }
    sheets = {
        (s["division_id"], s["subject_id"]): s
        for s in db.marks_sheets.find({"academic_year_id": year_id, "subject_id": {"$in": list(subjects)}})
    }
    out = []
    for division_id, subject_id in pairs:
        subject, division = subjects.get(subject_id), divisions.get(division_id)
        if not subject or not division:
            continue
        scheme = schemes.get(subject_id)
        s = sheets.get((division_id, subject_id))
        size = db.students.count_documents({"division_id": division_id, "status": "active"})
        complete = sum(1 for m in (s or {}).get("marks", {}).values() if scheme and total_of(m, scheme) is not None)
        out.append(
            {
                "division_id": str(division_id),
                "class": timetable._division_label(division),
                "subject_id": str(subject_id),
                "code": subject["code"],
                "name": subject["name"],
                "has_scheme": bool(scheme),
                "deadline": scheme.get("deadline") if scheme else None,
                "status": s["status"] if s else "draft",
                "status_label": STATUS_LABELS[s["status"] if s else "draft"],
                "complete": complete,
                "students": size,
            }
        )
    return sorted(out, key=lambda r: (r["class"], r["code"]))


def my_classes(ctx: AuthContext) -> list[dict[str, Any]]:
    return _rows(ctx, _pairs_for({"faculty_ids": ctx.user_id}))


def department_sheets(ctx: AuthContext) -> list[dict[str, Any]]:
    """HOD: every class-subject of their department; Exam Cell / readers: everything."""
    db = get_db()
    if P.EXAMS_MANAGE in ctx.permissions or P.MARKS_READ in ctx.permissions:
        return _rows(ctx, _pairs_for({}))
    dept = ctx.user.get("department_id")
    if P.MARKS_APPROVE not in ctx.permissions or not dept:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    programmes = [p["_id"] for p in db.programmes.find({"department_id": dept}, {"_id": 1})]
    divisions = [d["_id"] for d in db.divisions.find({"programme_id": {"$in": programmes}}, {"_id": 1})]
    return _rows(ctx, _pairs_for({"division_id": {"$in": divisions}}))


def my_marks(ctx: AuthContext) -> list[dict[str, Any]]:
    """A student's own internal marks, once the teacher has published them."""
    from app.modules.students import service as students

    student = students.my_student(ctx)
    db = get_db()
    year_id = current_year_id()
    out = []
    for s in db.marks_sheets.find(
        {
            "division_id": student.get("division_id"),
            "academic_year_id": year_id,
            "status": {"$in": sorted(VISIBLE_TO_STUDENTS)},
        }
    ):
        scheme = db.assessment_schemes.find_one({"_id": s["scheme_id"]})
        subject = db.subjects.find_one({"_id": s["subject_id"]}, {"code": 1, "name": 1, "max_internal": 1})
        if not scheme or not subject:
            continue
        entry = s["marks"].get(str(student["_id"]), {})
        out.append(
            {
                "subject_id": str(subject["_id"]),
                "code": subject["code"],
                "name": subject["name"],
                "out_of": subject["max_internal"],
                "status": s["status"],
                "components": [
                    {"name": c["name"], "max": c["max"], "mark": entry.get(c["key"])} for c in scheme["components"]
                ],
                "total": total_of(entry, scheme),
            }
        )
    return sorted(out, key=lambda x: x["code"])


def round_up(total: float) -> int:
    """University uploads take whole marks; a fraction is rounded up."""
    return math.ceil(total)
