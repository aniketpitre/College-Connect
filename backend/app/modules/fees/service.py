"""Fee heads, fee structures, demand generation, charges and a student's fee account."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.modules.fees import ledger
from app.modules.fees.schemas import (
    ChargeIn,
    FeeHeadIn,
    FeeHeadUpdate,
    GenerateDemands,
    StructureFields,
    StructureIn,
    StructureUpdate,
)
from app.modules.students import service as students

register_indexes("fee_heads", [IndexModel([("code", ASCENDING)], unique=True)])
register_indexes(
    "fee_structures",
    [
        IndexModel(
            [
                ("academic_year_id", ASCENDING),
                ("programme_id", ASCENDING),
                ("year_of_study", ASCENDING),
                ("category_key", ASCENDING),
            ],
            unique=True,
        )
    ],
)

STARTER_HEADS = [
    ("TUITION", "Tuition fee"),
    ("DEV", "Development fee"),
    ("EXAM", "Examination fee"),
    ("LIB", "Library fee"),
    ("GYM", "Gymkhana fee"),
    ("UNIV", "University fees"),
    ("LATE", "Late fee"),
]


def oid(value: Any, what: str, field: str | None = None) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AppError(404 if field is None else 422, f"{what} not found.", field=field) from e


def find(collection: str, record_id: ObjectId, what: str, field: str | None = None, session=None) -> dict[str, Any]:
    doc = get_db()[collection].find_one({"_id": record_id}, session=session)
    if not doc:
        raise AppError(404 if field is None else 422, f"{what} not found.", field=field)
    return doc


def jsonable(value: Any) -> Any:
    return students.jsonable(value)


# --- fee heads ------------------------------------------------------------------------------


def head_view(h: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(h["_id"]), "code": h["code"], "name": h["name"], "status": h.get("status", "active")}


def list_heads() -> list[dict[str, Any]]:
    return [head_view(h) for h in get_db().fee_heads.find().sort("code", ASCENDING)]


def create_head(ctx: AuthContext, body: FeeHeadIn, ip: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        "code": body.code,
        "name": body.name.strip(),
        "status": "active",
        "created_at": now,
        "created_by": ctx.user_id,
    }
    try:
        doc["_id"] = get_db().fee_heads.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "A fee head with this code exists.", "conflict", "code") from e
    audit.record(
        "fees.head.created",
        actor_id=ctx.user_id,
        target_type="fee_head",
        target_id=doc["_id"],
        ip=ip,
        details={"code": body.code},
    )
    return head_view(doc)


def update_head(ctx: AuthContext, head_id: str, body: FeeHeadUpdate, ip: str) -> dict[str, Any]:
    hid = oid(head_id, "Fee head")
    before = find("fee_heads", hid, "Fee head")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        get_db().fee_heads.update_one({"_id": hid}, {"$set": changes})
        audit.record(
            "fees.head.updated",
            actor_id=ctx.user_id,
            target_type="fee_head",
            target_id=hid,
            ip=ip,
            details={"before": head_view(before), "after": changes},
        )
    return head_view(find("fee_heads", hid, "Fee head"))


def load_starter_heads(ctx: AuthContext, ip: str) -> dict[str, int]:
    created = 0
    for code, name in STARTER_HEADS:
        result = get_db().fee_heads.update_one(
            {"code": code},
            {
                "$setOnInsert": {
                    "name": name,
                    "status": "active",
                    "created_at": datetime.now(UTC),
                    "created_by": ctx.user_id,
                }
            },
            upsert=True,
        )
        created += 1 if result.upserted_id else 0
    audit.record("fees.head.starter_loaded", actor_id=ctx.user_id, ip=ip, details={"created": created})
    return {"created": created}


def _late_head() -> ObjectId:
    head = get_db().fee_heads.find_one_and_update(
        {"code": "LATE"},
        {"$setOnInsert": {"name": "Late fee", "status": "active", "created_at": datetime.now(UTC)}},
        upsert=True,
        return_document=True,
    )
    assert head is not None  # upsert always returns the document
    return head["_id"]


# --- fee structures -------------------------------------------------------------------------


def structure_view(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(s["_id"]),
        "academic_year_id": str(s["academic_year_id"]),
        "programme_id": str(s["programme_id"]),
        "year_of_study": s["year_of_study"],
        "category_id": str(s["category_id"]) if s.get("category_id") else None,
        "name": s["name"],
        "items": [{"head_id": str(i["head_id"]), "amount": i["amount"]} for i in s["items"]],
        "installments": s["installments"],
        "late_fee": s.get("late_fee", 0),
        "total": sum(i["amount"] for i in s["items"]),
        "locked": bool(s.get("locked")),
        "status": s.get("status", "active"),
    }


def list_structures(academic_year_id: str | None, programme_id: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if academic_year_id:
        query["academic_year_id"] = oid(academic_year_id, "Academic year")
    if programme_id:
        query["programme_id"] = oid(programme_id, "Programme")
    rows = get_db().fee_structures.find(query).sort([("programme_id", ASCENDING), ("year_of_study", ASCENDING)])
    return [structure_view(s) for s in rows]


def _structure_fields(body: StructureFields) -> dict[str, Any]:
    items = []
    for item in body.items:
        head = find("fee_heads", oid(item.head_id, "Fee head", "items"), "Fee head", "items")
        if head.get("status") != "active":
            raise AppError(422, f"Fee head {head['code']} is archived.", field="items")
        items.append({"head_id": head["_id"], "amount": item.amount})
    return {
        "name": body.name.strip(),
        "items": items,
        "installments": [
            {"label": i.label, "due_date": i.due_date.isoformat(), "amount": i.amount} for i in body.installments
        ],
        "late_fee": body.late_fee,
    }


def create_structure(ctx: AuthContext, body: StructureIn, ip: str) -> dict[str, Any]:
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )
    programme = find("programmes", oid(body.programme_id, "Programme", "programme_id"), "Programme", "programme_id")
    if body.year_of_study > programme["duration_years"]:
        raise AppError(422, f"{programme['code']} has {programme['duration_years']} years.", field="year_of_study")
    category_id = None
    if body.category_id:
        category_id = find("categories", oid(body.category_id, "Category", "category_id"), "Category", "category_id")[
            "_id"
        ]
    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        **_structure_fields(body),
        "academic_year_id": year["_id"],
        "programme_id": programme["_id"],
        "year_of_study": body.year_of_study,
        "category_id": category_id,
        "category_key": str(category_id) if category_id else "*",
        "status": "active",
        "locked": False,
        "created_at": now,
        "created_by": ctx.user_id,
    }
    try:
        doc["_id"] = get_db().fee_structures.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(
            409, "A fee structure for this class and category already exists for this year.", "conflict", "category_id"
        ) from e
    audit.record(
        "fees.structure.created",
        actor_id=ctx.user_id,
        target_type="fee_structure",
        target_id=doc["_id"],
        ip=ip,
        details={"after": jsonable(structure_view(doc))},
    )
    return structure_view(doc)


def update_structure(ctx: AuthContext, structure_id: str, body: StructureUpdate, ip: str) -> dict[str, Any]:
    sid = oid(structure_id, "Fee structure")
    before = find("fee_structures", sid, "Fee structure")
    if before.get("locked"):
        raise AppError(
            409,
            "Fees were already charged from this structure. "
            "Change a student's fees with a charge or a concession instead.",
            "locked",
        )
    changes = _structure_fields(body)
    get_db().fee_structures.update_one(
        {"_id": sid}, {"$set": {**changes, "updated_at": datetime.now(UTC), "updated_by": ctx.user_id}}
    )
    after = find("fee_structures", sid, "Fee structure")
    audit.record(
        "fees.structure.updated",
        actor_id=ctx.user_id,
        target_type="fee_structure",
        target_id=sid,
        ip=ip,
        details={"before": jsonable(structure_view(before)), "after": jsonable(structure_view(after))},
    )
    return structure_view(after)


# --- demands --------------------------------------------------------------------------------


def generate_demands(ctx: AuthContext, body: GenerateDemands, ip: str) -> dict[str, Any]:
    """Charges each active student of a class the year's fee from their category's structure
    (or the class's default structure). Students already charged for the year are skipped."""
    db = get_db()
    year = find("academic_years", oid(body.academic_year_id, "Academic year"), "Academic year")
    programme = find("programmes", oid(body.programme_id, "Programme"), "Programme")
    structures = {
        s["category_key"]: s
        for s in db.fee_structures.find(
            {
                "academic_year_id": year["_id"],
                "programme_id": programme["_id"],
                "year_of_study": body.year_of_study,
                "status": "active",
            }
        )
    }
    roster = list(
        db.students.find(
            {"programme_id": programme["_id"], "year_of_study": body.year_of_study, "status": "active"}
        ).sort("prn", ASCENDING)
    )
    charged = {
        e["student_id"]
        for e in db.ledger_entries.find(
            {"type": "demand", "academic_year_id": year["_id"], "student_id": {"$in": [s["_id"] for s in roster]}},
            {"student_id": 1},
        )
    }
    plan = []
    for s in roster:
        structure = structures.get(str(s.get("category_id"))) or structures.get("*")
        if s["_id"] in charged:
            outcome = "already_charged"
        elif not structure:
            outcome = "no_structure"
        else:
            outcome = "charge"
        plan.append((s, structure, outcome))
    result = {
        "academic_year": year["name"],
        "class": f"{programme['code']} {programme['year_labels'][body.year_of_study - 1]}",
        "students": [
            {
                "id": str(s["_id"]),
                "prn": s["prn"],
                "name": s["name"],
                "outcome": outcome,
                "structure": structure["name"] if structure else None,
                "amount": sum(i["amount"] for i in structure["items"]) if structure else 0,
            }
            for s, structure, outcome in plan
        ],
        "counts": {k: sum(1 for *_, o in plan if o == k) for k in ("charge", "already_charged", "no_structure")},
        "total": sum(sum(i["amount"] for i in st["items"]) for _, st, o in plan if o == "charge" and st),
        "dry_run": body.dry_run,
    }
    if body.dry_run:
        return result

    def work(session: ClientSession) -> None:
        used = set()
        for s, structure, outcome in plan:
            if outcome != "charge" or structure is None:
                continue
            ledger.post(
                student_id=s["_id"],
                academic_year_id=year["_id"],
                type="demand",
                lines=[{"head_id": i["head_id"], "amount": i["amount"]} for i in structure["items"]],
                created_by=ctx.user_id,
                session=session,
                ref={"type": "fee_structure", "id": structure["_id"]},
                demand_key=f"{s['_id']}:{year['_id']}",
                installments=structure["installments"],
                late_fee=structure.get("late_fee", 0),
                structure_name=structure["name"],
            )
            used.add(structure["_id"])
        if used:
            db.fee_structures.update_many({"_id": {"$in": list(used)}}, {"$set": {"locked": True}}, session=session)
        audit.record(
            "fees.demands.generated",
            actor_id=ctx.user_id,
            ip=ip,
            session=session,
            details={
                "class": result["class"],
                "academic_year": year["name"],
                "students": result["counts"]["charge"],
                "total": result["total"],
            },
        )

    try:
        run_in_transaction(work)
    except DuplicateKeyError as e:
        raise AppError(
            409, "Another user charged some of these students at the same moment. Try again.", "conflict"
        ) from e
    return result


def add_charge(ctx: AuthContext, student_id: str, body: ChargeIn, ip: str) -> dict[str, Any]:
    """An extra amount a student owes (late fee, fine, lost ID card), with a reason."""
    student = students.get_student(oid(student_id, "Student"))
    year = find(
        "academic_years",
        oid(body.academic_year_id, "Academic year", "academic_year_id"),
        "Academic year",
        "academic_year_id",
    )
    head = find("fee_heads", oid(body.head_id, "Fee head", "head_id"), "Fee head", "head_id")

    def work(session: ClientSession) -> None:
        entry = ledger.post(
            student_id=student["_id"],
            academic_year_id=year["_id"],
            type="charge",
            lines=[{"head_id": head["_id"], "amount": body.amount}],
            created_by=ctx.user_id,
            session=session,
            reason=body.reason.strip(),
        )
        audit.record(
            "fees.charge.added",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            reason=body.reason,
            details={"entry_id": str(entry["_id"]), "head": head["code"], "amount": body.amount},
            session=session,
        )

    run_in_transaction(work)
    return account(student["_id"], year["_id"])


def apply_late_fees(ctx: AuthContext, student_id: str, academic_year_id: str, ip: str) -> dict[str, Any]:
    """Charges the structure's late fee once for each overdue installment not yet charged."""
    student = students.get_student(oid(student_id, "Student"))
    year = find("academic_years", oid(academic_year_id, "Academic year"), "Academic year")
    rows = ledger.entries(student["_id"], year["_id"])
    info = ledger.summary(rows)
    if not info["late_fee"]:
        raise AppError(409, "This student's fee structure has no late fee.", "conflict")
    already = {e.get("late_fee_for") for e in rows if e["type"] == "charge" and e.get("late_fee_for")}
    due = [i["label"] for i in info["installments"] if i["overdue"] and i["label"] not in already]
    if not due:
        raise AppError(409, "No overdue installment without a late fee.", "conflict")
    late_head = _late_head()

    def work(session: ClientSession) -> None:
        for label in due:
            ledger.post(
                student_id=student["_id"],
                academic_year_id=year["_id"],
                type="charge",
                lines=[{"head_id": late_head, "amount": info["late_fee"]}],
                created_by=ctx.user_id,
                session=session,
                reason=f"Late fee: {label} overdue",
                late_fee_for=label,
            )
        audit.record(
            "fees.late_fee.applied",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            details={"installments": due, "each": info["late_fee"]},
            session=session,
        )

    run_in_transaction(work)
    return account(student["_id"], year["_id"])


# --- a student's account --------------------------------------------------------------------


def _heads() -> dict[ObjectId, dict[str, Any]]:
    return {h["_id"]: h for h in get_db().fee_heads.find()}


def entry_view(e: dict[str, Any], heads: dict[ObjectId, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(e["_id"]),
        "at": e["at"].isoformat(),
        "type": e["type"],
        "label": ledger.LABELS.get(e["type"], e["type"]),
        "amount": e["amount"],
        "lines": [{"head": heads.get(ln["head_id"], {}).get("code", "?"), "amount": ln["amount"]} for ln in e["lines"]],
        "reason": e.get("reason"),
        "receipt_number": e.get("receipt_number"),
        "receipt_id": str(e["ref"]["id"]) if e.get("ref", {}).get("type") == "receipt" else None,
        "reverses": str(e["reverses"]) if e.get("reverses") else None,
        "reversed": bool(e.get("reversed")),
    }


def account(student_id: ObjectId, academic_year_id: ObjectId) -> dict[str, Any]:
    """Everything the Accounts screen shows about one student's year."""
    rows = ledger.entries(student_id, academic_year_id)
    heads = _heads()
    info = ledger.summary(rows)
    outstanding = ledger.by_head(rows)
    order = ledger.head_order(rows)
    return {
        "student_id": str(student_id),
        "academic_year_id": str(academic_year_id),
        **info,
        "by_head": [
            {
                "head_id": str(h),
                "code": heads.get(h, {}).get("code", "?"),
                "name": heads.get(h, {}).get("name", "?"),
                "outstanding": outstanding[h],
            }
            for h in order + [h for h in outstanding if h not in order]
            if h in outstanding
        ],
        "entries": [entry_view(e, heads) for e in rows],
        "has_demand": any(e["type"] == "demand" for e in rows),
    }
