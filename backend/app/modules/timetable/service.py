"""
Weekly timetable per division and term (spec §3.7, plan 2.1).

A timetable belongs to one division for one term of an academic year and is valid between two
dates. Its slots repeat every week (day + start/end time). Each slot is checked against every
other active slot that overlaps in dates, day and time: the same faculty member, the same room,
or the same division (unless both are different practical batches) is a clash.

A one-day change to a slot (cancelled, or taken by a substitute) is a "change"; students see it.
Dates are ISO strings (YYYY-MM-DD), like the rest of the setup data.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import STAFF_ROLES, P
from app.modules.timetable.schemas import ChangeIn, SlotIn, TimetableIn, TimetableUpdate

register_indexes(
    "timetables",
    [IndexModel([("division_id", ASCENDING), ("academic_year_id", ASCENDING), ("term", ASCENDING)], unique=True)],
)
register_indexes(
    "timetable_slots",
    [
        IndexModel([("status", ASCENDING), ("day", ASCENDING)]),
        IndexModel([("timetable_id", ASCENDING)]),
        IndexModel([("faculty_ids", ASCENDING), ("day", ASCENDING)]),
    ],
)
register_indexes("timetable_changes", [IndexModel([("slot_id", ASCENDING), ("date", ASCENDING)], unique=True)])

DAYS = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TEACHING_ROLES = {"faculty", "hod", "mentor", "principal"}


def oid(value: Any, what: str, field: str | None = None) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AppError(404 if field is None else 422, f"{what} not found.", field=field) from e


def _find(collection: str, value: Any, what: str, field: str | None = None) -> dict[str, Any]:
    doc = get_db()[collection].find_one({"_id": value if isinstance(value, ObjectId) else oid(value, what, field)})
    if not doc:
        raise AppError(404 if field is None else 422, f"{what} not found.", field=field)
    return doc


# --- scope ---------------------------------------------------------------------------------


def department_of(division: dict[str, Any]) -> ObjectId | None:
    programme = get_db().programmes.find_one({"_id": division["programme_id"]}, {"department_id": 1})
    return programme.get("department_id") if programme else None


def can_manage(ctx: AuthContext, division: dict[str, Any]) -> bool:
    if P.TIMETABLE_MANAGE in ctx.permissions:
        return True
    dept = ctx.user.get("department_id")
    return P.TIMETABLE_MANAGE_DEPT in ctx.permissions and dept is not None and department_of(division) == dept


def _require_manage(ctx: AuthContext, division: dict[str, Any]) -> None:
    if not can_manage(ctx, division):
        raise AppError(403, "You can only change timetables of your own department.", "forbidden")


# --- views ---------------------------------------------------------------------------------


def _names(ids: list[ObjectId]) -> dict[ObjectId, str]:
    return {u["_id"]: u["name"] for u in get_db().users.find({"_id": {"$in": ids}}, {"name": 1})}


def _division_label(division: dict[str, Any], programme: dict[str, Any] | None = None) -> str:
    programme = programme or get_db().programmes.find_one({"_id": division["programme_id"]}) or {}
    labels = programme.get("year_labels", [])
    year = division["year_of_study"]
    year_label = labels[year - 1] if len(labels) >= year else str(year)
    return f"{programme.get('code', '')} {year_label} {division['name']}".strip()


def slot_view(
    s: dict[str, Any], names: dict[ObjectId, str], subjects: dict[ObjectId, dict[str, Any]]
) -> dict[str, Any]:
    subject = subjects.get(s["subject_id"], {})
    return {
        "id": str(s["_id"]),
        "timetable_id": str(s["timetable_id"]),
        "division_id": str(s["division_id"]),
        "day": s["day"],
        "day_name": DAYS[s["day"]],
        "start": s["start"],
        "end": s["end"],
        "subject_id": str(s["subject_id"]),
        "subject_code": subject.get("code"),
        "subject_name": subject.get("name"),
        "subject_type": subject.get("type"),
        "faculty_ids": [str(f) for f in s["faculty_ids"]],
        "faculty": [names.get(f, "?") for f in s["faculty_ids"]],
        "room": s.get("room", ""),
        "batch": s.get("batch"),
    }


def _slot_views(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    db = get_db()
    names = _names(list({f for s in slots for f in s["faculty_ids"]}))
    subjects = {x["_id"]: x for x in db.subjects.find({"_id": {"$in": list({s["subject_id"] for s in slots})}})}
    return [slot_view(s, names, subjects) for s in slots]


def view(t: dict[str, Any], ctx: AuthContext | None = None) -> dict[str, Any]:
    db = get_db()
    division = db.divisions.find_one({"_id": t["division_id"]}) or {}
    year = db.academic_years.find_one({"_id": t["academic_year_id"]}, {"name": 1}) or {}
    slots = list(
        db.timetable_slots.find({"timetable_id": t["_id"], "status": "active"}).sort([("day", 1), ("start", 1)])
    )
    return {
        "id": str(t["_id"]),
        "academic_year_id": str(t["academic_year_id"]),
        "academic_year": year.get("name"),
        "division_id": str(t["division_id"]),
        "division": _division_label(division) if division else None,
        "term": t["term"],
        "semester": t["semester"],
        "valid_from": t["valid_from"],
        "valid_to": t["valid_to"],
        "can_manage": bool(ctx and division and can_manage(ctx, division)),
        "slots": _slot_views(slots),
    }


# --- timetables ----------------------------------------------------------------------------


def _year_and_division(
    academic_year_id: str, division_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    year = _find("academic_years", academic_year_id, "Academic year", "academic_year_id")
    division = _find("divisions", division_id, "Division", "division_id")
    if division.get("status") == "archived":
        raise AppError(422, "This division is archived.", field="division_id")
    programme = _find("programmes", division["programme_id"], "Programme")
    return year, division, programme


def create_timetable(ctx: AuthContext, body: TimetableIn, ip: str) -> dict[str, Any]:
    year, division, programme = _year_and_division(body.academic_year_id, body.division_id)
    _require_manage(ctx, division)
    if body.term > programme["semesters_per_year"]:
        raise AppError(422, f"{programme['code']} has {programme['semesters_per_year']} terms a year.", field="term")
    valid_from, valid_to = body.valid_from.isoformat(), body.valid_to.isoformat()
    if not (year["start_date"] <= valid_from and valid_to <= year["end_date"]):
        raise AppError(422, f"The dates must fall inside academic year {year['name']}.", field="valid_from")
    now = datetime.now(UTC)
    doc = {
        "academic_year_id": year["_id"],
        "division_id": division["_id"],
        "programme_id": programme["_id"],
        "term": body.term,
        "semester": (division["year_of_study"] - 1) * programme["semesters_per_year"] + body.term,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "created_by": ctx.user_id,
        "created_at": now,
        "updated_at": now,
    }
    try:
        doc["_id"] = get_db().timetables.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "This division already has a timetable for that term.", "conflict") from e
    audit.record(
        "timetable.created",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=doc["_id"],
        ip=ip,
        details={"division": _division_label(division, programme), "term": body.term},
    )
    return view(doc, ctx)


def get_timetable(timetable_id: str) -> dict[str, Any]:
    return _find("timetables", timetable_id, "Timetable")


def update_timetable(ctx: AuthContext, timetable_id: str, body: TimetableUpdate, ip: str) -> dict[str, Any]:
    t = get_timetable(timetable_id)
    division = _find("divisions", t["division_id"], "Division")
    _require_manage(ctx, division)
    year = _find("academic_years", t["academic_year_id"], "Academic year")
    valid_from = body.valid_from.isoformat() if body.valid_from else t["valid_from"]
    valid_to = body.valid_to.isoformat() if body.valid_to else t["valid_to"]
    if valid_to < valid_from:
        raise AppError(422, "The end date must be on or after the start date.", field="valid_to")
    if not (year["start_date"] <= valid_from and valid_to <= year["end_date"]):
        raise AppError(422, f"The dates must fall inside academic year {year['name']}.", field="valid_from")
    db = get_db()
    slots = list(db.timetable_slots.find({"timetable_id": t["_id"], "status": "active"}))
    for s in slots:  # longer dates can create clashes with other timetables
        _check_clash({**s, "valid_from": valid_from, "valid_to": valid_to}, exclude={x["_id"] for x in slots})
    db.timetables.update_one(
        {"_id": t["_id"]},
        {"$set": {"valid_from": valid_from, "valid_to": valid_to, "updated_at": datetime.now(UTC)}},
    )
    db.timetable_slots.update_many(
        {"timetable_id": t["_id"]}, {"$set": {"valid_from": valid_from, "valid_to": valid_to}}
    )
    audit.record(
        "timetable.dates_changed",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        details={"before": [t["valid_from"], t["valid_to"]], "after": [valid_from, valid_to]},
    )
    return view(get_timetable(timetable_id), ctx)


def list_timetables(ctx: AuthContext, academic_year_id: str | None, division_id: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if academic_year_id:
        query["academic_year_id"] = oid(academic_year_id, "Academic year", "academic_year_id")
    if division_id:
        query["division_id"] = oid(division_id, "Division", "division_id")
    db = get_db()
    rows = list(db.timetables.find(query).sort([("valid_from", -1)]).limit(300))
    divisions = {d["_id"]: d for d in db.divisions.find({"_id": {"$in": [r["division_id"] for r in rows]}})}
    programmes = {p["_id"]: p for p in db.programmes.find({})}
    counts = {
        c["_id"]: c["n"]
        for c in db.timetable_slots.aggregate(
            [
                {"$match": {"timetable_id": {"$in": [r["_id"] for r in rows]}, "status": "active"}},
                {"$group": {"_id": "$timetable_id", "n": {"$sum": 1}}},
            ]
        )
    }
    result = []
    for r in rows:
        d = divisions.get(r["division_id"], {})
        result.append(
            {
                "id": str(r["_id"]),
                "division_id": str(r["division_id"]),
                "division": _division_label(d, programmes.get(d.get("programme_id"))) if d else None,
                "academic_year_id": str(r["academic_year_id"]),
                "term": r["term"],
                "semester": r["semester"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
                "slots": counts.get(r["_id"], 0),
                "can_manage": bool(d and can_manage(ctx, d)),
            }
        )
    return result


# --- slots ---------------------------------------------------------------------------------


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start < b_end and b_start < a_end


def _check_clash(slot: dict[str, Any], exclude: set[ObjectId] | None = None) -> None:
    """Raises 409 naming the first clash with another active slot."""
    exclude = exclude or set()
    db = get_db()
    candidates = db.timetable_slots.find(
        {
            "status": "active",
            "day": slot["day"],
            "valid_from": {"$lte": slot["valid_to"]},
            "valid_to": {"$gte": slot["valid_from"]},
            "start": {"$lt": slot["end"]},
            "end": {"$gt": slot["start"]},
        }
    )
    for other in candidates:
        if other["_id"] in exclude or other["_id"] == slot.get("_id"):
            continue
        when = f"{DAYS[other['day']]} {other['start']}–{other['end']}"
        shared = set(other["faculty_ids"]) & set(slot["faculty_ids"])
        if shared:
            who = ", ".join(_names(list(shared)).values())
            raise AppError(409, f"{who} already teaches another class on {when}.", "clash", "faculty_ids")
        if slot.get("room") and other.get("room") == slot["room"]:
            raise AppError(409, f"Room {slot['room']} is already used on {when}.", "clash", "room")
        if other["division_id"] == slot["division_id"]:
            batches = (other.get("batch"), slot.get("batch"))
            if None in batches or batches[0] == batches[1]:
                raise AppError(409, f"This division already has a lecture on {when}.", "clash", "start")


def _slot_doc(t: dict[str, Any], body: SlotIn) -> dict[str, Any]:
    db = get_db()
    subject = _find("subjects", body.subject_id, "Subject", "subject_id")
    if subject["programme_id"] != t["programme_id"] or subject["semester"] != t["semester"]:
        raise AppError(422, f"Choose a subject of semester {t['semester']}.", field="subject_id")
    faculty_ids = list(dict.fromkeys(oid(f, "Teacher", "faculty_ids") for f in body.faculty_ids))
    staff = db.users.count_documents({"_id": {"$in": faculty_ids}, "kind": "staff", "status": "active"})
    if staff != len(faculty_ids):
        raise AppError(422, "Choose active staff members.", field="faculty_ids")
    return {
        "timetable_id": t["_id"],
        "division_id": t["division_id"],
        "academic_year_id": t["academic_year_id"],
        "day": body.day,
        "start": body.start,
        "end": body.end,
        "subject_id": subject["_id"],
        "faculty_ids": faculty_ids,
        "room": body.room,
        "batch": body.batch,
        "valid_from": t["valid_from"],
        "valid_to": t["valid_to"],
        "status": "active",
    }


def add_slot(ctx: AuthContext, timetable_id: str, body: SlotIn, ip: str) -> dict[str, Any]:
    t = get_timetable(timetable_id)
    _require_manage(ctx, _find("divisions", t["division_id"], "Division"))
    doc = _slot_doc(t, body)
    _check_clash(doc)
    doc["created_at"] = doc["updated_at"] = datetime.now(UTC)
    doc["_id"] = get_db().timetable_slots.insert_one(doc).inserted_id
    audit.record(
        "timetable.slot_added",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        details={"day": body.day, "start": body.start, "subject_id": str(doc["subject_id"])},
    )
    return _slot_views([doc])[0]


def get_slot(slot_id: str) -> dict[str, Any]:
    return _find("timetable_slots", slot_id, "Lecture")


def update_slot(ctx: AuthContext, slot_id: str, body: SlotIn, ip: str) -> dict[str, Any]:
    old = get_slot(slot_id)
    if old["status"] != "active":
        raise AppError(409, "This lecture was removed.", "conflict")
    t = get_timetable(str(old["timetable_id"]))
    _require_manage(ctx, _find("divisions", t["division_id"], "Division"))
    doc = {**_slot_doc(t, body), "_id": old["_id"]}
    _check_clash(doc)
    doc["updated_at"] = datetime.now(UTC)
    get_db().timetable_slots.update_one({"_id": old["_id"]}, {"$set": {k: v for k, v in doc.items() if k != "_id"}})
    audit.record(
        "timetable.slot_changed",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        details={
            "before": {k: old.get(k) for k in ("day", "start", "end", "room", "batch")},
            "after": {k: doc.get(k) for k in ("day", "start", "end", "room", "batch")},
        },
    )
    return _slot_views([{**old, **doc}])[0]


def remove_slot(ctx: AuthContext, slot_id: str, ip: str) -> None:
    """Removed slots are kept (attendance taken in them still points at them)."""
    old = get_slot(slot_id)
    t = get_timetable(str(old["timetable_id"]))
    _require_manage(ctx, _find("divisions", t["division_id"], "Division"))
    get_db().timetable_slots.update_one(
        {"_id": old["_id"]}, {"$set": {"status": "removed", "updated_at": datetime.now(UTC)}}
    )
    audit.record(
        "timetable.slot_removed",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        details={"day": old["day"], "start": old["start"]},
    )


# --- one-day changes -----------------------------------------------------------------------


def set_change(ctx: AuthContext, slot_id: str, body: ChangeIn, ip: str) -> dict[str, Any]:
    slot = get_slot(slot_id)
    t = get_timetable(str(slot["timetable_id"]))
    _require_manage(ctx, _find("divisions", t["division_id"], "Division"))
    day = body.date.isoformat()
    if body.date.isoweekday() != slot["day"] or not slot["valid_from"] <= day <= slot["valid_to"]:
        raise AppError(422, f"This lecture isn't held on {body.date:%d %b %Y}.", field="date")
    faculty_ids = [oid(f, "Teacher", "faculty_ids") for f in body.faculty_ids] if body.kind == "substitute" else []
    if faculty_ids:
        if get_db().users.count_documents({"_id": {"$in": faculty_ids}, "kind": "staff", "status": "active"}) != len(
            faculty_ids
        ):
            raise AppError(422, "Choose active staff members.", field="faculty_ids")
        busy = [x for x in lectures_on(body.date, faculty_id=None) if set(x["_faculty"]) & set(faculty_ids)]
        busy = [
            x for x in busy if x["slot_id"] != slot_id and _overlaps(x["start"], x["end"], slot["start"], slot["end"])
        ]
        if busy:
            raise AppError(409, "The substitute already has a lecture at that time.", "clash", "faculty_ids")
    doc = {
        "slot_id": slot["_id"],
        "date": day,
        "kind": body.kind,
        "faculty_ids": faculty_ids,
        "room": body.room.strip().upper(),
        "reason": body.reason.strip(),
        "created_by": ctx.user_id,
        "created_at": datetime.now(UTC),
    }
    get_db().timetable_changes.replace_one({"slot_id": slot["_id"], "date": day}, doc, upsert=True)
    audit.record(
        f"timetable.lecture_{body.kind}",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        reason=body.reason,
        details={"date": day, "slot_id": slot_id},
    )
    return {"slot_id": slot_id, "date": day, "kind": body.kind}


def remove_change(ctx: AuthContext, slot_id: str, day: date, ip: str) -> None:
    slot = get_slot(slot_id)
    t = get_timetable(str(slot["timetable_id"]))
    _require_manage(ctx, _find("divisions", t["division_id"], "Division"))
    result = get_db().timetable_changes.delete_one({"slot_id": slot["_id"], "date": day.isoformat()})
    if not result.deleted_count:
        raise AppError(404, "No change on that day.")
    audit.record(
        "timetable.change_undone",
        actor_id=ctx.user_id,
        target_type="timetable",
        target_id=t["_id"],
        ip=ip,
        details={"date": day.isoformat(), "slot_id": slot_id},
    )


# --- lectures on a day / in a week ---------------------------------------------------------


def holidays_between(first: date, last: date) -> dict[str, str]:
    return {
        h["date"]: h["name"]
        for h in get_db().holidays.find(
            {"date": {"$gte": first.isoformat(), "$lte": last.isoformat()}, "status": {"$ne": "archived"}},
            {"date": 1, "name": 1},
        )
    }


def lectures_on(
    day: date,
    *,
    faculty_id: ObjectId | None = None,
    division_ids: list[ObjectId] | None = None,
    include_cancelled: bool = True,
) -> list[dict[str, Any]]:
    """Lectures held on `day`, with that day's changes applied. A faculty filter also finds
    lectures they take as a substitute. Empty on Sundays and holidays."""
    weekday = day.isoweekday()
    if weekday == 7 or holidays_between(day, day):
        return []
    iso = day.isoformat()
    db = get_db()
    query: dict[str, Any] = {"status": "active", "day": weekday, "valid_from": {"$lte": iso}, "valid_to": {"$gte": iso}}
    if division_ids is not None:
        query["division_id"] = {"$in": division_ids}
    changes = {c["slot_id"]: c for c in db.timetable_changes.find({"date": iso})}
    if faculty_id is not None:
        substituting = [sid for sid, c in changes.items() if faculty_id in c.get("faculty_ids", [])]
        query["$or"] = [{"faculty_ids": faculty_id}, {"_id": {"$in": substituting}}]
    slots = list(db.timetable_slots.find(query).sort([("start", 1), ("end", 1)]))
    views = _slot_views(slots)
    names = _names(list({f for c in changes.values() for f in c.get("faculty_ids", [])}))
    divisions = {d["_id"]: d for d in db.divisions.find({"_id": {"$in": list({s["division_id"] for s in slots})}})}
    programmes = {p["_id"]: p for p in db.programmes.find({}, {"code": 1, "year_labels": 1})}
    result = []
    for s, v in zip(slots, views, strict=True):
        change = changes.get(s["_id"])
        status = change["kind"] if change else "scheduled"
        if (
            faculty_id is not None
            and change
            and change["kind"] == "substitute"
            and faculty_id not in change["faculty_ids"]
        ):
            status = "handed_over"  # someone else takes it today
        if status == "cancelled" and not include_cancelled:
            continue
        teacher_ids = change["faculty_ids"] if change and change["kind"] == "substitute" else s["faculty_ids"]
        d = divisions.get(s["division_id"], {})
        result.append(
            {
                **v,
                "slot_id": v["id"],
                "date": iso,
                "status": status,
                "division": _division_label(d, programmes.get(d.get("programme_id"))) if d else None,
                "substitute": [names.get(f, "?") for f in change["faculty_ids"]]
                if change and change["faculty_ids"]
                else [],
                "room": (change or {}).get("room") or v["room"],
                "change_reason": change["reason"] if change else None,
                "_faculty": teacher_ids,
            }
        )
    return result


def public(lecture: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in lecture.items() if not k.startswith("_")}


def week(
    start: date, *, faculty_id: ObjectId | None = None, division_ids: list[ObjectId] | None = None
) -> dict[str, Any]:
    monday = start - timedelta(days=start.isoweekday() - 1)
    days = [monday + timedelta(days=i) for i in range(6)]
    holidays = holidays_between(days[0], days[-1])
    return {
        "week_of": monday.isoformat(),
        "days": [
            {
                "date": d.isoformat(),
                "day_name": DAYS[d.isoweekday()],
                "holiday": holidays.get(d.isoformat()),
                "lectures": [public(x) for x in lectures_on(d, faculty_id=faculty_id, division_ids=division_ids)],
            }
            for d in days
        ],
    }


# --- options for the editor ----------------------------------------------------------------


def options(timetable_id: str) -> dict[str, Any]:
    t = get_timetable(timetable_id)
    db = get_db()
    subjects = db.subjects.find(
        {"programme_id": t["programme_id"], "semester": t["semester"], "status": {"$ne": "archived"}}
    ).sort("code", ASCENDING)
    teachers = db.users.find(
        {
            "kind": "staff",
            "status": "active",
            "roles": {"$in": sorted(TEACHING_ROLES & {r.value for r in STAFF_ROLES})},
        },
        {"name": 1, "department_id": 1},
    ).sort("name", ASCENDING)
    rooms = sorted(r for r in db.timetable_slots.distinct("room", {"status": "active"}) if r)
    return {
        "subjects": [
            {"id": str(s["_id"]), "code": s["code"], "name": s["name"], "type": s.get("type", "theory")}
            for s in subjects
        ],
        "faculty": [
            {
                "id": str(u["_id"]),
                "name": u["name"],
                "department_id": str(u["department_id"]) if u.get("department_id") else None,
            }
            for u in teachers
        ],
        "rooms": rooms,
    }
