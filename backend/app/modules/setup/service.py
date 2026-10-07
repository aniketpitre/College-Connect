"""
Institution setup (spec §3.1): academic years, departments, programmes, divisions, subjects,
categories, holidays and the college's own details.

Records are never deleted: they are archived (status "archived") so older students, fees and
marks keep pointing at valid data. Every change is written to the audit log with before/after.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.modules.setup.schemas import InstitutionSettings


@dataclass(frozen=True)
class Entity:
    collection: str
    label: str
    sort: list[tuple[str, int]]
    unique: tuple[str, ...]  # fields of the unique index, for the "already exists" message
    refs: dict[str, str] = field(default_factory=dict)  # field -> referenced collection


ENTITIES: dict[str, Entity] = {
    "academic_years": Entity("academic_years", "Academic year", [("name", DESCENDING)], ("name",)),
    "departments": Entity("departments", "Department", [("code", ASCENDING)], ("code",)),
    "programmes": Entity(
        "programmes", "Programme", [("code", ASCENDING)], ("code",), refs={"department_id": "departments"}
    ),
    "divisions": Entity(
        "divisions",
        "Division",
        [("programme_id", ASCENDING), ("year_of_study", ASCENDING), ("name", ASCENDING)],
        ("programme_id", "year_of_study", "name"),
        refs={"programme_id": "programmes"},
    ),
    "subjects": Entity(
        "subjects",
        "Subject",
        [("programme_id", ASCENDING), ("semester", ASCENDING), ("code", ASCENDING)],
        ("programme_id", "code"),
        refs={"programme_id": "programmes"},
    ),
    "categories": Entity("categories", "Category", [("code", ASCENDING)], ("code",)),
    "holidays": Entity(
        "holidays",
        "Holiday",
        [("date", ASCENDING)],
        ("academic_year_id", "date"),
        refs={"academic_year_id": "academic_years"},
    ),
}

for _e in ENTITIES.values():
    register_indexes(_e.collection, [IndexModel([(f, ASCENDING) for f in _e.unique], unique=True)])
register_indexes("academic_years", [IndexModel([("is_current", ASCENDING)])])

SETTINGS_ID = "institution"

# Maharashtra admission categories (editable after loading).
STARTER_CATEGORIES = [
    ("OPEN", "Open"),
    ("OBC", "Other Backward Class"),
    ("SC", "Scheduled Caste"),
    ("ST", "Scheduled Tribe"),
    ("VJ-NT", "Vimukta Jati / Nomadic Tribes"),
    ("SBC", "Special Backward Class"),
    ("SEBC", "Socially and Educationally Backward Class"),
    ("EWS", "Economically Weaker Section"),
]


def oid(value: Any, what: str = "Record", field_name: str | None = None) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AppError(404 if field_name is None else 422, f"{what} not found.", field=field_name) from e


def out(doc: dict[str, Any]) -> dict[str, Any]:
    """JSON-friendly copy: ObjectIds as strings, `_id` as `id`, audit fields dropped."""
    result: dict[str, Any] = {"id": str(doc["_id"])}
    for key, value in doc.items():
        if key in {"_id", "created_by", "updated_by"}:
            continue
        if isinstance(value, ObjectId):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        result[key] = value
    return result


def _plain(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}


def _get(entity: Entity, record_id: ObjectId) -> dict[str, Any]:
    doc = get_db()[entity.collection].find_one({"_id": record_id})
    if not doc:
        raise AppError(404, f"{entity.label} not found.")
    return doc


def _resolve_refs(entity: Entity, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Turns reference ids into ObjectIds and checks that they point at active records."""
    found: dict[str, dict[str, Any]] = {}
    for ref_field, collection in entity.refs.items():
        if ref_field not in data or data[ref_field] is None:
            continue
        label = ENTITIES[collection].label
        ref_id = oid(data[ref_field], label, ref_field)
        doc = get_db()[collection].find_one({"_id": ref_id})
        if not doc:
            raise AppError(422, f"{label} not found.", field=ref_field)
        if doc.get("status") == "archived":
            raise AppError(422, f"{label} {doc.get('code') or doc.get('name')} is archived.", field=ref_field)
        data[ref_field] = ref_id
        found[ref_field] = doc
    return found


def _check_rules(entity_name: str, data: dict[str, Any], refs: dict[str, dict[str, Any]]) -> None:
    if entity_name == "divisions":
        programme = refs["programme_id"]
        if data["year_of_study"] > programme["duration_years"]:
            raise AppError(422, f"{programme['code']} has {programme['duration_years']} years.", field="year_of_study")
    if entity_name == "subjects":
        programme = refs["programme_id"]
        semesters = programme["duration_years"] * programme["semesters_per_year"]
        if data["semester"] > semesters:
            raise AppError(422, f"{programme['code']} has {semesters} semesters.", field="semester")
    if entity_name == "holidays":
        year = refs["academic_year_id"]
        if not year["start_date"] <= data["date"] <= year["end_date"]:
            raise AppError(422, f"The date is outside academic year {year['name']}.", field="date")


def list_records(entity_name: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    entity = ENTITIES[entity_name]
    query = {k: v for k, v in (filters or {}).items() if v is not None}
    for ref_field in entity.refs:
        if ref_field in query:
            query[ref_field] = oid(query[ref_field], ENTITIES[entity.refs[ref_field]].label)
    return [out(d) for d in get_db()[entity.collection].find(query).sort(entity.sort)]


def create(ctx: AuthContext, entity_name: str, body: BaseModel, ip: str) -> dict[str, Any]:
    entity = ENTITIES[entity_name]
    data = _plain(body.model_dump())
    refs = _resolve_refs(entity, data)
    _check_rules(entity_name, data, refs)
    now = datetime.now(UTC)
    doc = {**data, "status": "active", "created_at": now, "created_by": ctx.user_id, "updated_at": now}
    if entity_name == "academic_years":
        doc["is_current"] = False
    try:
        doc["_id"] = get_db()[entity.collection].insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, f"This {entity.label.lower()} already exists.", "conflict", entity.unique[-1]) from e
    audit.record(
        f"setup.{entity_name}.created",
        actor_id=ctx.user_id,
        target_type=entity_name,
        target_id=doc["_id"],
        ip=ip,
        details={"after": out(doc)},
    )
    return out(doc)


def update(ctx: AuthContext, entity_name: str, record_id: str, body: BaseModel, ip: str) -> dict[str, Any]:
    entity = ENTITIES[entity_name]
    rid = oid(record_id, entity.label)
    before = _get(entity, rid)
    changes = _plain(body.model_dump(exclude_unset=True))
    if not changes:
        return out(before)
    refs = _resolve_refs(entity, changes)
    merged = {**before, **changes}
    if entity_name in {"divisions", "subjects", "holidays"}:
        all_refs = refs or _resolve_refs(entity, {k: before[k] for k in entity.refs})
        _check_rules(entity_name, merged, all_refs)
    if entity_name == "academic_years":
        if merged["end_date"] <= merged["start_date"]:
            raise AppError(422, "The end date must be after the start date.", field="end_date")
        if changes.get("status") == "archived" and before.get("is_current"):
            raise AppError(409, "Make another year current before archiving this one.", "conflict", "status")
    if entity_name == "programmes" and "year_labels" in changes:
        labels = [x.strip().upper() for x in changes["year_labels"] if x.strip()]
        if len(labels) != before["duration_years"]:
            raise AppError(422, "Give one label per year of the programme.", field="year_labels")
        changes["year_labels"] = labels
    changes["updated_at"] = datetime.now(UTC)
    changes["updated_by"] = ctx.user_id
    get_db()[entity.collection].update_one({"_id": rid}, {"$set": changes})
    after = _get(entity, rid)
    audit.record(
        f"setup.{entity_name}.updated",
        actor_id=ctx.user_id,
        target_type=entity_name,
        target_id=rid,
        ip=ip,
        details={"before": out(before), "after": out(after)},
    )
    return out(after)


def make_current(ctx: AuthContext, record_id: str, ip: str) -> dict[str, Any]:
    entity = ENTITIES["academic_years"]
    rid = oid(record_id, entity.label)
    year = _get(entity, rid)
    if year.get("status") == "archived":
        raise AppError(409, "This academic year is archived.", "conflict")
    db = get_db()

    def switch(session) -> None:
        db.academic_years.update_many({"is_current": True}, {"$set": {"is_current": False}}, session=session)
        db.academic_years.update_one({"_id": rid}, {"$set": {"is_current": True}}, session=session)
        audit.record(
            "setup.academic_years.made_current",
            actor_id=ctx.user_id,
            target_type="academic_years",
            target_id=rid,
            ip=ip,
            session=session,
        )

    run_in_transaction(switch)
    return out(_get(entity, rid))


def current_year() -> dict[str, Any] | None:
    return get_db().academic_years.find_one({"is_current": True})


def institution() -> dict[str, Any]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID}) or {}
    fields = InstitutionSettings.model_fields
    return {name: doc.get(name, "" if f.is_required() else f.default) for name, f in fields.items()}


def public_profile() -> dict[str, Any]:
    """What the public home page may show: no people, no money, nothing private."""
    db = get_db()
    inst = institution()
    depts = {d["_id"]: d["name"] for d in db.departments.find({"status": "active"}, {"name": 1})}
    programmes = [
        {
            "code": p["code"],
            "name": p["name"],
            "level": p.get("level", "UG"),
            "duration_years": p.get("duration_years"),
            "department": depts.get(p.get("department_id"), ""),
        }
        for p in db.programmes.find({"status": "active"}).sort("code", ASCENDING)
    ]
    keep = ("name", "short_name", "address", "phone", "email", "website", "university")
    return {**{k: inst.get(k) or "" for k in keep}, "programmes": programmes, "departments": len(depts)}


def save_institution(ctx: AuthContext, body: InstitutionSettings, ip: str) -> dict[str, Any]:
    before = institution()
    data = body.model_dump()
    data["email"] = str(data["email"]) if data["email"] else None
    get_db().settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {**data, "updated_at": datetime.now(UTC), "updated_by": ctx.user_id}},
        upsert=True,
    )
    audit.record(
        "setup.institution.updated",
        actor_id=ctx.user_id,
        target_type="settings",
        target_id=SETTINGS_ID,
        ip=ip,
        details={"before": before, "after": data},
    )
    return institution()


def overview() -> dict[str, Any]:
    """Everything a screen needs for dropdowns, in one call (subjects are fetched per programme)."""
    current = current_year()
    return {
        "institution": institution(),
        "current_year": out(current) if current else None,
        **{
            name: list_records(name)
            for name in ("academic_years", "departments", "programmes", "divisions", "categories")
        },
    }


def load_starter_data(ctx: AuthContext, ip: str) -> dict[str, int]:
    """Standard categories, a Computer Science department with BCA (FY/SY/TY, division A) and the
    current academic year. Skips anything that already exists, so it is safe to run twice."""
    db = get_db()
    now = datetime.now(UTC)
    created = {"categories": 0, "departments": 0, "programmes": 0, "divisions": 0, "academic_years": 0}
    meta = {"status": "active", "created_at": now, "created_by": ctx.user_id, "updated_at": now}

    def insert(collection: str, key: dict[str, Any], doc: dict[str, Any]) -> ObjectId:
        existing = db[collection].find_one(key)
        if existing:
            return existing["_id"]
        created[collection] += 1
        return db[collection].insert_one({**key, **doc, **meta}).inserted_id

    for code, name in STARTER_CATEGORIES:
        insert("categories", {"code": code}, {"name": name, "reserved_percent": None})
    dept = insert("departments", {"code": "CS"}, {"name": "Computer Science"})
    bca = insert(
        "programmes",
        {"code": "BCA"},
        {
            "name": "Bachelor of Computer Applications",
            "department_id": dept,
            "level": "UG",
            "duration_years": 3,
            "semesters_per_year": 2,
            "year_labels": ["FY", "SY", "TY"],
        },
    )
    for year in (1, 2, 3):
        insert("divisions", {"programme_id": bca, "year_of_study": year, "name": "A"}, {"capacity": 60})
    if not db.academic_years.count_documents({}):
        today = date.today()
        start = today.year if today.month >= 6 else today.year - 1
        insert(
            "academic_years",
            {"name": f"{start}-{(start + 1) % 100:02d}"},
            {"start_date": f"{start}-06-01", "end_date": f"{start + 1}-05-31", "is_current": True},
        )
    audit.record("setup.starter_data.loaded", actor_id=ctx.user_id, ip=ip, details=created)
    return created
