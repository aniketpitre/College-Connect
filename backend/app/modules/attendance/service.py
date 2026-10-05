"""
Lecture attendance (spec §3.7, plan 2.2).

One record per lecture held (`attendance_sessions`, unique per timetable slot and date) with the
class list at that moment (`roster`) and who was absent (`absent`). Everyone else was present.

- Teachers of the lecture that day (incl. a substitute) mark it, up to 48 hours after it ends.
  Later changes go to the HOD as an edit request; the HOD of the department may change it at
  any time (audited).
- Each save carries the version the device last saw. A different version on the server means
  someone else saved in between (e.g. an offline phone syncing late): 409 with the server copy.
- Exemptions (medical / official duty) entered by the office cover a date range; an exempted
  absence counts as attended in the percentages (2.4).
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.attendance.schemas import EditRequestIn, ExemptionIn, MarkIn
from app.modules.timetable import service as timetable

register_indexes(
    "attendance_sessions",
    [
        IndexModel([("slot_id", ASCENDING), ("date", ASCENDING)], unique=True),
        IndexModel([("roster", ASCENDING), ("date", ASCENDING)]),
        IndexModel([("division_id", ASCENDING), ("date", ASCENDING)]),
    ],
)
register_indexes(
    "attendance_edit_requests",
    [
        IndexModel([("status", ASCENDING), ("requested_at", ASCENDING)]),
        IndexModel([("open_key", ASCENDING)], unique=True, partialFilterExpression={"open_key": {"$type": "string"}}),
    ],
)
register_indexes("attendance_exemptions", [IndexModel([("student_id", ASCENDING), ("from_date", ASCENDING)])])

EDIT_WINDOW = timedelta(hours=48)
KINDS = {"medical": "Medical", "official_duty": "Official duty"}


# --- the lecture and who may touch it -------------------------------------------------------


def _division(division_id: ObjectId) -> dict[str, Any]:
    division = get_db().divisions.find_one({"_id": division_id})
    if not division:
        raise AppError(404, "Class not found.")
    return division


def lecture(slot_id: str, day: date) -> dict[str, Any]:
    """The lecture as held on `day` (changes applied); 404 if it isn't held then."""
    slot = timetable.get_slot(slot_id)
    for x in timetable.lectures_on(day, division_ids=[slot["division_id"]]):
        if x["slot_id"] == slot_id:
            return x
    raise AppError(404, "This lecture isn't held on that day.")


def is_hod_for(ctx: AuthContext, division: dict[str, Any]) -> bool:
    dept = ctx.user.get("department_id")
    return P.ATTENDANCE_APPROVE in ctx.permissions and dept is not None and timetable.department_of(division) == dept


def teaches(ctx: AuthContext, lec: dict[str, Any]) -> bool:
    return P.ATTENDANCE_TAKE in ctx.permissions and ctx.user_id in lec["_faculty"]


def can_read_division(ctx: AuthContext, division: dict[str, Any]) -> bool:
    if P.ATTENDANCE_READ in ctx.permissions:
        return True
    dept = ctx.user.get("department_id")
    if P.ATTENDANCE_READ_DEPT in ctx.permissions and dept and timetable.department_of(division) == dept:
        return True
    # Teachers read the classes they teach.
    return P.ATTENDANCE_TAKE in ctx.permissions and bool(
        get_db().timetable_slots.find_one({"division_id": division["_id"], "faculty_ids": ctx.user_id}, {"_id": 1})
    )


def deadline(lec: dict[str, Any]) -> datetime:
    day = date.fromisoformat(lec["date"])
    hour, minute = (int(x) for x in lec["end"].split(":"))
    return datetime.combine(day, time(hour, minute), clock.IST) + EDIT_WINDOW


# --- class list -----------------------------------------------------------------------------


def _roll_key(s: dict[str, Any]) -> tuple[int, str, str]:
    roll = (s.get("roll_no") or "").strip()
    return (int(roll) if roll.isdigit() else 10**9, roll, s["name"])


def roster(slot: dict[str, Any]) -> list[dict[str, Any]]:
    """Active students of the class; for a practical batch, only that batch (if batches are set)."""
    db = get_db()
    fields = {"name": 1, "prn": 1, "roll_no": 1, "batch": 1, "photo_file_id": 1}
    students = list(db.students.find({"division_id": slot["division_id"], "status": "active"}, fields))
    if slot.get("batch") and any(s.get("batch") == slot["batch"] for s in students):
        students = [s for s in students if s.get("batch") == slot["batch"]]
    return sorted(students, key=_roll_key)


def students_for(slot: dict[str, Any], day: date) -> list[dict[str, Any]]:
    """The class list for a save: a lecture already marked keeps the list it was taken with."""
    existing = get_db().attendance_sessions.find_one({"slot_id": slot["_id"], "date": day.isoformat()}, {"roster": 1})
    if not existing:
        return roster(slot)
    return list(get_db().students.find({"_id": {"$in": existing["roster"]}}, {"name": 1}))


def exemptions_on(student_ids: list[ObjectId], day: date) -> dict[ObjectId, str]:
    iso = day.isoformat()
    rows = get_db().attendance_exemptions.find(
        {"student_id": {"$in": student_ids}, "status": "active", "from_date": {"$lte": iso}, "to_date": {"$gte": iso}}
    )
    return {r["student_id"]: r["kind"] for r in rows}


def session_view(s: dict[str, Any] | None) -> dict[str, Any] | None:
    if not s:
        return None
    by = get_db().users.find_one({"_id": s.get("updated_by") or s["taken_by"]}, {"name": 1}) or {}
    return {
        "id": str(s["_id"]),
        "absent": [str(x) for x in s["absent"]],
        "present": len(s["roster"]) - len(s["absent"]),
        "total": len(s["roster"]),
        "version": s["version"],
        "saved_by": by.get("name"),
        "saved_at": (s.get("updated_at") or s["created_at"]).isoformat(),
    }


def today(ctx: AuthContext, day: date) -> dict[str, Any]:
    """The signed-in teacher's lectures on `day`, with what's been marked."""
    lectures = timetable.lectures_on(day, faculty_id=ctx.user_id)
    db = get_db()
    sessions = {
        s["slot_id"]: s
        for s in db.attendance_sessions.find(
            {"slot_id": {"$in": [ObjectId(x["slot_id"]) for x in lectures]}, "date": day.isoformat()}
        )
    }
    now = clock.now()
    rows = []
    for x in lectures:
        s = sessions.get(ObjectId(x["slot_id"]))
        rows.append(
            {
                **timetable.public(x),
                "takeable": x["status"] in ("scheduled", "substitute") and teaches(ctx, x) and day <= clock.today(),
                "editable_until": deadline(x).isoformat(),
                "window_open": now <= deadline(x),
                "session": {"present": len(s["roster"]) - len(s["absent"]), "total": len(s["roster"])} if s else None,
            }
        )
    holiday = timetable.holidays_between(day, day).get(day.isoformat())
    return {"date": day.isoformat(), "holiday": holiday, "lectures": rows}


def sheet(ctx: AuthContext, slot_id: str, day: date) -> dict[str, Any]:
    """Everything the take-attendance screen needs (also cached on the phone for offline use)."""
    lec = lecture(slot_id, day)
    slot = timetable.get_slot(slot_id)
    division = _division(slot["division_id"])
    hod = is_hod_for(ctx, division)
    if not (teaches(ctx, lec) or hod or can_read_division(ctx, division)):
        raise AppError(403, "You don't teach this lecture.", "forbidden")
    students = roster(slot)
    exempt = exemptions_on([s["_id"] for s in students], day)
    session = get_db().attendance_sessions.find_one({"slot_id": slot["_id"], "date": day.isoformat()})
    in_window = clock.now() <= deadline(lec)
    return {
        "lecture": timetable.public(lec),
        "students": [
            {
                "id": str(s["_id"]),
                "name": s["name"],
                "prn": s["prn"],
                "roll_no": s.get("roll_no"),
                "photo_url": f"/files/{s['photo_file_id']}" if s.get("photo_file_id") else None,
                "exempt": exempt.get(s["_id"]),
            }
            for s in students
        ],
        "session": session_view(session),
        "can_save": lec["status"] != "cancelled"
        and day <= clock.today()
        and (hod or (teaches(ctx, lec) and in_window)),
        "can_request_edit": teaches(ctx, lec) and not hod and not in_window,
        "editable_until": deadline(lec).isoformat(),
    }


# --- saving ---------------------------------------------------------------------------------


def _absent_ids(absent: list[str], students: list[dict[str, Any]]) -> list[ObjectId]:
    on_list = {s["_id"] for s in students}
    ids = []
    for value in dict.fromkeys(absent):
        try:
            sid = ObjectId(value)
        except Exception as e:
            raise AppError(422, "Unknown student in the absent list.", field="absent") from e
        if sid not in on_list:
            raise AppError(422, "A student in the absent list isn't in this class.", field="absent")
        ids.append(sid)
    return ids


def _check_markable(lec: dict[str, Any], day: date) -> None:
    if lec["status"] == "cancelled":
        raise AppError(409, "This lecture was cancelled.", "cancelled")
    if day > clock.today():
        raise AppError(422, "Attendance can't be marked for a future day.", field="date")


def _write(
    ctx: AuthContext,
    slot: dict[str, Any],
    lec: dict[str, Any],
    day: date,
    students: list[dict[str, Any]],
    absent: list[ObjectId],
    *,
    base_version: int | None,
    client_id: str | None,
    ip: str,
    reason: str | None = None,
    via: str = "teacher",
) -> dict[str, Any]:
    db = get_db()
    iso = day.isoformat()
    now = clock.now()
    existing = db.attendance_sessions.find_one({"slot_id": slot["_id"], "date": iso})
    if existing:
        if client_id and existing.get("client_id") == client_id and existing["absent"] == absent:
            return existing  # the same offline save arriving twice
        if base_version != existing["version"]:
            raise AppError(
                409,
                "Someone else saved this lecture's attendance in the meantime. Check their version first.",
                "attendance_conflict",
            )
        updated = db.attendance_sessions.find_one_and_update(
            {"_id": existing["_id"], "version": existing["version"]},
            {
                "$set": {
                    "absent": absent,
                    "version": existing["version"] + 1,
                    "updated_by": ctx.user_id,
                    "updated_at": now,
                    **({"client_id": client_id} if client_id else {}),
                },
                "$push": {"history": {"at": now, "by": ctx.user_id, "absent_before": existing["absent"], "via": via}},
            },
            return_document=True,
        )
        if not updated:
            raise AppError(409, "Someone else saved this lecture's attendance in the meantime.", "attendance_conflict")
        action, doc = "attendance.changed", updated
    else:
        if base_version not in (None, 0):
            raise AppError(409, "This attendance was removed on the server.", "attendance_conflict")
        doc = {
            "slot_id": slot["_id"],
            "date": iso,
            "division_id": slot["division_id"],
            "academic_year_id": slot["academic_year_id"],
            "subject_id": slot["subject_id"],
            "batch": slot.get("batch"),
            "start": lec["start"],
            "end": lec["end"],
            "teacher_ids": lec["_faculty"],
            "roster": [s["_id"] for s in students],
            "absent": absent,
            "version": 1,
            "taken_by": ctx.user_id,
            "created_at": now,
            "history": [],
            **({"client_id": client_id} if client_id else {}),
        }
        try:
            doc["_id"] = db.attendance_sessions.insert_one(doc).inserted_id
        except DuplicateKeyError as e:
            raise AppError(409, "Someone else saved this lecture's attendance just now.", "attendance_conflict") from e
        action = "attendance.marked"
    audit.record(
        action,
        actor_id=ctx.user_id,
        target_type="attendance",
        target_id=doc["_id"],
        ip=ip,
        reason=reason,
        details={
            "date": iso,
            "subject": lec["subject_code"],
            "absent": len(absent),
            "total": len(students),
            "via": via,
        },
    )
    return doc


def save(ctx: AuthContext, body: MarkIn, ip: str) -> dict[str, Any]:
    lec = lecture(body.slot_id, body.date)
    _check_markable(lec, body.date)
    slot = timetable.get_slot(body.slot_id)
    division = _division(slot["division_id"])
    hod = is_hod_for(ctx, division)
    if not (teaches(ctx, lec) or hod):
        raise AppError(403, "You don't teach this lecture.", "forbidden")
    if not hod and clock.now() > deadline(lec):
        raise AppError(403, "The 48 hours to change this lecture are over. Ask your HOD.", "edit_window_closed")
    students = students_for(slot, body.date)
    absent = _absent_ids(body.absent, students)
    doc = _write(
        ctx,
        slot,
        lec,
        body.date,
        students,
        absent,
        base_version=body.base_version,
        client_id=body.client_id,
        ip=ip,
        via="hod" if hod and not teaches(ctx, lec) else "teacher",
    )
    view = session_view(doc)
    assert view is not None
    return view


# --- edits after 48 hours -------------------------------------------------------------------


def request_edit(ctx: AuthContext, body: EditRequestIn, ip: str) -> dict[str, Any]:
    lec = lecture(body.slot_id, body.date)
    _check_markable(lec, body.date)
    if not teaches(ctx, lec):
        raise AppError(403, "You don't teach this lecture.", "forbidden")
    if clock.now() <= deadline(lec):
        raise AppError(409, "You can still change this lecture yourself.", "window_open")
    slot = timetable.get_slot(body.slot_id)
    absent = _absent_ids(body.absent, roster(slot))
    doc = {
        "slot_id": slot["_id"],
        "date": body.date.isoformat(),
        "division_id": slot["division_id"],
        "absent": absent,
        "reason": body.reason.strip(),
        "status": "pending",
        "requested_by": ctx.user_id,
        "requested_at": clock.now(),
        "open_key": f"{slot['_id']}:{body.date.isoformat()}",
    }
    try:
        doc["_id"] = get_db().attendance_edit_requests.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "A change for this lecture is already waiting for the HOD.", "conflict") from e
    audit.record(
        "attendance.edit_requested",
        actor_id=ctx.user_id,
        target_type="attendance_request",
        target_id=doc["_id"],
        ip=ip,
        reason=body.reason,
        details={"date": doc["date"], "subject": lec["subject_code"]},
    )
    return _request_view(doc)


def _request_view(r: dict[str, Any], cache: dict[str, Any] | None = None) -> dict[str, Any]:
    db = get_db()
    cache = cache if cache is not None else {}
    slot = cache.get(r["slot_id"]) or db.timetable_slots.find_one({"_id": r["slot_id"]}) or {}
    subject = db.subjects.find_one({"_id": slot.get("subject_id")}, {"code": 1, "name": 1}) or {}
    division = db.divisions.find_one({"_id": r["division_id"]}) or {}
    names = {
        u["_id"]: u["name"]
        for u in db.users.find({"_id": {"$in": [r["requested_by"], r.get("decided_by")]}}, {"name": 1})
    }
    current = db.attendance_sessions.find_one({"slot_id": r["slot_id"], "date": r["date"]}, {"absent": 1})
    return {
        "id": str(r["_id"]),
        "slot_id": str(r["slot_id"]),
        "date": r["date"],
        "class": timetable._division_label(division) if division else None,
        "subject": f"{subject.get('code', '')} {subject.get('name', '')}".strip(),
        "start": slot.get("start"),
        "absent_now": len(current["absent"]) if current else None,
        "absent_new": len(r["absent"]),
        "reason": r["reason"],
        "status": r["status"],
        "requested_by": names.get(r["requested_by"]),
        "requested_by_id": str(r["requested_by"]),
        "requested_at": r["requested_at"].isoformat(),
        "decided_by": names.get(r.get("decided_by")),
        "decision_reason": r.get("decision_reason"),
    }


def list_requests(ctx: AuthContext, status: str | None) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {"status": status} if status else {}
    rows = list(db.attendance_edit_requests.find(query).sort("requested_at", DESCENDING).limit(200))
    divisions = {d["_id"]: d for d in db.divisions.find({"_id": {"$in": list({r["division_id"] for r in rows})}})}
    visible = [
        r
        for r in rows
        if r["requested_by"] == ctx.user_id
        or (r["division_id"] in divisions and is_hod_for(ctx, divisions[r["division_id"]]))
    ]
    return [_request_view(r) for r in visible]


def decide(ctx: AuthContext, request_id: str, approve: bool, reason: str | None, ip: str) -> dict[str, Any]:
    db = get_db()
    r = db.attendance_edit_requests.find_one({"_id": timetable.oid(request_id, "Request")})
    if not r:
        raise AppError(404, "Request not found.")
    if not is_hod_for(ctx, _division(r["division_id"])):
        raise AppError(403, "Only the HOD of this department decides.", "forbidden")
    if r["requested_by"] == ctx.user_id:
        raise AppError(403, "You can't approve your own request.", "same_person")
    if not approve and not (reason and reason.strip()):
        raise AppError(422, "Give a reason for rejecting.", field="reason")
    day = date.fromisoformat(r["date"])

    def work(session: Any) -> None:
        claimed = db.attendance_edit_requests.find_one_and_update(
            {"_id": r["_id"], "status": "pending"},
            {
                "$set": {
                    "status": "approved" if approve else "rejected",
                    "decided_by": ctx.user_id,
                    "decided_at": clock.now(),
                    "decision_reason": (reason or "").strip() or None,
                },
                "$unset": {"open_key": ""},
            },
            session=session,
        )
        if not claimed:
            raise AppError(409, "This request was already decided.", "conflict")

    run_in_transaction(work)
    if approve:
        slot = timetable.get_slot(str(r["slot_id"]))
        lec = lecture(str(r["slot_id"]), day)
        existing = db.attendance_sessions.find_one({"slot_id": slot["_id"], "date": r["date"]})
        students = students_for(slot, day)
        _write(
            ctx,
            slot,
            lec,
            day,
            students,
            [a for a in r["absent"] if a in {s["_id"] for s in students}],
            base_version=existing["version"] if existing else None,
            client_id=None,
            ip=ip,
            reason=r["reason"],
            via="hod_approved",
        )
    audit.record(
        f"attendance.edit_{'approved' if approve else 'rejected'}",
        actor_id=ctx.user_id,
        target_type="attendance_request",
        target_id=r["_id"],
        ip=ip,
        reason=reason,
    )
    doc = db.attendance_edit_requests.find_one({"_id": r["_id"]})
    assert doc is not None
    return _request_view(doc)


# --- exemptions -----------------------------------------------------------------------------


def _exemption_view(
    e: dict[str, Any], students: dict[ObjectId, dict[str, Any]], names: dict[ObjectId, str]
) -> dict[str, Any]:
    s = students.get(e["student_id"], {})
    return {
        "id": str(e["_id"]),
        "student_id": str(e["student_id"]),
        "student": s.get("name"),
        "prn": s.get("prn"),
        "kind": e["kind"],
        "kind_label": KINDS[e["kind"]],
        "from_date": e["from_date"],
        "to_date": e["to_date"],
        "reason": e["reason"],
        "status": e["status"],
        "entered_by": names.get(e["created_by"]),
        "created_at": e["created_at"].isoformat(),
    }


def add_exemption(ctx: AuthContext, body: ExemptionIn, ip: str) -> dict[str, Any]:
    db = get_db()
    student = db.students.find_one({"_id": timetable.oid(body.student_id, "Student", "student_id")})
    if not student:
        raise AppError(422, "Student not found.", field="student_id")
    doc = {
        "student_id": student["_id"],
        "kind": body.kind,
        "from_date": body.from_date.isoformat(),
        "to_date": body.to_date.isoformat(),
        "reason": body.reason.strip(),
        "status": "active",
        "created_by": ctx.user_id,
        "created_at": clock.now(),
    }
    doc["_id"] = db.attendance_exemptions.insert_one(doc).inserted_id
    audit.record(
        "attendance.exemption_added",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        reason=body.reason,
        details={"kind": body.kind, "from": doc["from_date"], "to": doc["to_date"]},
    )
    return _exemption_view(doc, {student["_id"]: student}, {ctx.user_id: ctx.user["name"]})


def list_exemptions(student_id: str | None) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {}
    if student_id:
        query["student_id"] = timetable.oid(student_id, "Student", "student_id")
    rows = list(db.attendance_exemptions.find(query).sort("from_date", DESCENDING).limit(300))
    students = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}}, {"name": 1, "prn": 1})
    }
    names = {
        u["_id"]: u["name"] for u in db.users.find({"_id": {"$in": list({r["created_by"] for r in rows})}}, {"name": 1})
    }
    return [_exemption_view(r, students, names) for r in rows]


def cancel_exemption(ctx: AuthContext, exemption_id: str, reason: str | None, ip: str) -> None:
    if not (reason and reason.strip()):
        raise AppError(422, "Give a reason.", field="reason")
    db = get_db()
    e = db.attendance_exemptions.find_one_and_update(
        {"_id": timetable.oid(exemption_id, "Exemption"), "status": "active"},
        {"$set": {"status": "cancelled", "cancelled_by": ctx.user_id, "cancelled_at": clock.now()}},
    )
    if not e:
        raise AppError(404, "Exemption not found.")
    audit.record(
        "attendance.exemption_cancelled",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=e["student_id"],
        ip=ip,
        reason=reason,
    )
