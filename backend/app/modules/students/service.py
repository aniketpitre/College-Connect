"""
Student Information System (spec §3.3).

- Creating a student creates their login (PRN + temporary password) in the same transaction.
- Aadhaar: only the last 4 digits are stored.
- Students can't edit their record; they ask for a correction, which the office approves.
- Every change is audited with before/after, so the full history is available.
- Scope: staff with students.read see all students; a student sees only their own record
  (the /me/student routes); files are served only to those two.
"""

import re
from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core import audit, files
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.rbac import P
from app.core.security import hash_password, temporary_password
from app.modules.students.schemas import ChangeRequestIn, StudentCreate, StudentUpdate
from app.modules.users import repo as users_repo

register_indexes(
    "students",
    [
        IndexModel([("prn", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("programme_id", ASCENDING), ("year_of_study", ASCENDING), ("division_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("name", ASCENDING)]),
    ],
)
register_indexes(
    "student_change_requests",
    [IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]), IndexModel([("student_id", ASCENDING)])],
)

REF_FIELDS = {"programme_id": "programmes", "division_id": "divisions", "category_id": "categories"}
# Copied to the login account so sign-in, password reset and the user list stay in step.
USER_FIELDS = ("name", "email", "phone")


def oid(value: Any, what: str = "Student") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AppError(404, f"{what} not found.") from e


def _plain(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def jsonable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def fields_to_doc(ctx: AuthContext, data: dict[str, Any]) -> dict[str, Any]:
    """Validated request fields → stored fields (ids as ObjectIds, Aadhaar as last 4, consent record)."""
    doc: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"reason", "prn"}:
            continue
        if key == "aadhaar":
            doc["aadhaar_last4"] = value
        elif key == "guardian_consent":
            doc["guardian_consent"] = {"recorded": bool(value), "by": ctx.user_id, "at": datetime.now(UTC)}
        elif key in REF_FIELDS and value is not None:
            doc[key] = oid(value, REF_FIELDS[key][:-1].title())
        elif key == "email" and value is not None:
            doc[key] = str(value).lower()
        else:
            doc[key] = _plain(value)
    return doc


def check_placement(merged: dict[str, Any]) -> None:
    """Programme, year, division and category must exist, be active and fit together."""
    db = get_db()
    programme = db.programmes.find_one({"_id": merged.get("programme_id")})
    if not programme or programme.get("status") != "active":
        raise AppError(422, "Programme not found.", field="programme_id")
    if not 1 <= merged.get("year_of_study", 0) <= programme["duration_years"]:
        raise AppError(422, f"{programme['code']} has {programme['duration_years']} years.", field="year_of_study")
    if merged.get("division_id"):
        division = db.divisions.find_one({"_id": merged["division_id"]})
        if (
            not division
            or division.get("status") != "active"
            or division["programme_id"] != programme["_id"]
            or division["year_of_study"] != merged["year_of_study"]
        ):
            raise AppError(422, "That division is not part of this programme and year.", field="division_id")
    if merged.get("category_id"):
        category = db.categories.find_one({"_id": merged["category_id"]})
        if not category or category.get("status") != "active":
            raise AppError(422, "Category not found.", field="category_id")


def _lookups() -> dict[str, dict[Any, dict[str, Any]]]:
    db = get_db()
    return {
        "programmes": {d["_id"]: d for d in db.programmes.find({}, {"code": 1, "name": 1, "year_labels": 1})},
        "divisions": {d["_id"]: d for d in db.divisions.find({}, {"name": 1})},
        "categories": {d["_id"]: d for d in db.categories.find({}, {"code": 1, "name": 1})},
    }


def summary(doc: dict[str, Any], lookups: dict[str, dict[Any, dict[str, Any]]] | None = None) -> dict[str, Any]:
    lookups = lookups or _lookups()
    programme = lookups["programmes"].get(doc.get("programme_id"), {})
    year = doc.get("year_of_study")
    labels = programme.get("year_labels", [])
    division = lookups["divisions"].get(doc.get("division_id"), {})
    category = lookups["categories"].get(doc.get("category_id"), {})
    return {
        "id": str(doc["_id"]),
        "prn": doc["prn"],
        "name": doc["name"],
        "phone": doc.get("phone"),
        "email": doc.get("email"),
        "programme_id": str(doc["programme_id"]) if doc.get("programme_id") else None,
        "programme_code": programme.get("code"),
        "year_of_study": year,
        "year_label": labels[year - 1] if year and len(labels) >= year else None,
        "division_id": str(doc["division_id"]) if doc.get("division_id") else None,
        "division": division.get("name"),
        "roll_no": doc.get("roll_no"),
        "batch": doc.get("batch"),
        "category_code": category.get("code"),
        "status": doc.get("status", "active"),
        "has_photo": bool(doc.get("photo_file_id")),
    }


def view(doc: dict[str, Any]) -> dict[str, Any]:
    """The full record as the API returns it (to office staff, or to the student themselves)."""
    lookups = _lookups()
    result = summary(doc, lookups)
    programme = lookups["programmes"].get(doc.get("programme_id"), {})
    category = lookups["categories"].get(doc.get("category_id"), {})
    consent = doc.get("guardian_consent") or {}
    result.update(
        {
            "user_id": str(doc["user_id"]),
            "programme_name": programme.get("name"),
            "category_id": str(doc["category_id"]) if doc.get("category_id") else None,
            "category_name": category.get("name"),
            "mother_name": doc.get("mother_name"),
            "gender": doc.get("gender"),
            "dob": doc.get("dob"),
            "apaar_id": doc.get("apaar_id"),
            "aadhaar_masked": f"XXXX XXXX {doc['aadhaar_last4']}" if doc.get("aadhaar_last4") else None,
            "address": doc.get("address"),
            "guardian": doc.get("guardian"),
            "previous_education": doc.get("previous_education"),
            "admission_date": doc.get("admission_date"),
            "guardian_consent": bool(consent.get("recorded")),
            "photo_url": f"/files/{doc['photo_file_id']}" if doc.get("photo_file_id") else None,
            "documents": [
                {
                    "id": str(d["id"]),
                    "type": d["type"],
                    "filename": d.get("filename"),
                    "status": d["status"],
                    "reason": d.get("reason"),
                    "uploaded_at": d["uploaded_at"].isoformat(),
                    "url": f"/files/{d['file_id']}",
                }
                for d in doc.get("documents", [])
            ],
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
            "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
        }
    )
    return result


def get_student(student_id: ObjectId, session: ClientSession | None = None) -> dict[str, Any]:
    doc = get_db().students.find_one({"_id": student_id}, session=session)
    if not doc:
        raise AppError(404, "Student not found.")
    return doc


def my_student(ctx: AuthContext) -> dict[str, Any]:
    """The signed-in student's record; for a parent, the linked child they picked."""
    if ctx.user.get("kind") == "parent":
        from app.modules.parents import service as parents

        return parents.child(ctx)
    if ctx.user.get("kind") != "student":
        raise AppError(403, "This is for student accounts.", "forbidden")
    doc = get_db().students.find_one({"user_id": ctx.user_id})
    if not doc:
        raise AppError(404, "Your student record isn't set up yet. Please contact the college office.")
    return doc


# --- create / update -------------------------------------------------------------------------


def create(ctx: AuthContext, body: StudentCreate, ip: str) -> dict[str, Any]:
    data = body.model_dump(exclude_none=True)
    fields = fields_to_doc(ctx, data)
    fields.setdefault("status", "active")
    check_placement(fields)
    temp = temporary_password()
    doc = run_in_transaction(lambda session: insert(ctx, body.prn, body.name, fields, temp, ip, session))
    return {"student": view(doc), "temporary_password": temp}


def insert(
    ctx: AuthContext,
    prn: str,
    name: str,
    fields: dict[str, Any],
    temp: str,
    ip: str | None,
    session: ClientSession,
    *,
    documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inside a transaction: the student's login (temporary password) and their record."""
    db = get_db()
    user = users_repo.create_user(
        kind="student",
        name=name,
        roles=["student"],
        password_hash=hash_password(temp),
        must_change_password=True,
        created_by=ctx.user_id,
        prn=prn,
        email=fields.get("email"),
        phone=fields.get("phone"),
        session=session,
    )
    now = datetime.now(UTC)
    doc = {
        **fields,
        "prn": prn,
        "user_id": user["_id"],
        "documents": documents or [],
        "created_at": now,
        "created_by": ctx.user_id,
        "updated_at": now,
    }
    try:
        doc["_id"] = db.students.insert_one(doc, session=session).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "A student with this PRN already exists.", "conflict", "prn") from e
    audit.record(
        "students.created",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=doc["_id"],
        ip=ip,
        details={"after": jsonable(fields)},
        session=session,
    )
    return doc


def apply_changes(
    ctx: AuthContext,
    student: dict[str, Any],
    changes: dict[str, Any],
    *,
    action: str,
    ip: str,
    reason: str | None,
    session: ClientSession,
) -> None:
    """Writes changed fields to the record (and login account), audited with before/after."""
    changed = {k: v for k, v in changes.items() if student.get(k) != v}
    if not changed:
        return
    db = get_db()
    now = datetime.now(UTC)
    db.students.update_one(
        {"_id": student["_id"]}, {"$set": {**changed, "updated_at": now, "updated_by": ctx.user_id}}, session=session
    )
    user_changes = {k: changed[k] for k in USER_FIELDS if k in changed}
    if user_changes:
        unset = {k: "" for k, v in user_changes.items() if v is None}
        update: dict[str, Any] = {
            "$set": {**{k: v for k, v in user_changes.items() if v is not None}, "updated_at": now}
        }
        if unset:
            update["$unset"] = unset
        try:
            db.users.update_one({"_id": student["user_id"]}, update, session=session)
        except DuplicateKeyError as e:
            raise AppError(409, "Another account already uses this email.", "conflict", "email") from e
    audit.record(
        action,
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        reason=reason,
        details={
            "before": jsonable({k: student.get(k) for k in changed}),
            "after": jsonable(changed),
        },
        session=session,
    )


def update(ctx: AuthContext, student_id: ObjectId, body: StudentUpdate, ip: str) -> dict[str, Any]:
    student = get_student(student_id)
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason", None)
    changes = fields_to_doc(ctx, data)
    if "status" in changes and changes["status"] != student.get("status") and not reason:
        raise AppError(422, "Give a reason for changing the student's status.", field="reason")
    merged = {**student, **changes}
    if ("year_of_study" in changes or "programme_id" in changes) and "division_id" not in changes:
        merged["division_id"] = changes["division_id"] = None  # the old division belongs to the old class
    check_placement(merged)

    def work(session: ClientSession) -> None:
        apply_changes(ctx, student, changes, action="students.updated", ip=ip, reason=reason, session=session)

    run_in_transaction(work)
    return view(get_student(student_id))


def list_students(
    *,
    search: str | None,
    programme_id: str | None,
    year_of_study: int | None,
    division_id: str | None,
    status: str | None,
    skip: int,
    limit: int,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search and search.strip():
        q = re.escape(search.strip())
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"prn": {"$regex": f"^{q}", "$options": "i"}},
            {"phone": {"$regex": f"^{q}"}},
            {"email": {"$regex": f"^{q}", "$options": "i"}},
        ]
    if programme_id:
        query["programme_id"] = oid(programme_id, "Programme")
    if year_of_study:
        query["year_of_study"] = year_of_study
    if division_id:
        query["division_id"] = oid(division_id, "Division")
    if status:
        query["status"] = status
    db = get_db()
    total = db.students.count_documents(query)
    rows = db.students.find(query).sort([("prn", ASCENDING)]).skip(skip).limit(limit)
    lookups = _lookups()
    return {"items": [summary(d, lookups) for d in rows], "total": total}


def history(student_id: ObjectId) -> list[dict[str, Any]]:
    get_student(student_id)
    db = get_db()
    entries = list(
        db.audit_log.find({"target_type": "student", "target_id": student_id}).sort("at", DESCENDING).limit(200)
    )
    names = {
        u["_id"]: u["name"] for u in db.users.find({"_id": {"$in": [e.get("actor_id") for e in entries]}}, {"name": 1})
    }
    return [
        {
            "at": e["at"].isoformat(),
            "action": e["action"],
            "by": names.get(e.get("actor_id")),
            "reason": e.get("reason"),
            "details": jsonable(e.get("details")),
        }
        for e in entries
    ]


# --- change requests -------------------------------------------------------------------------


def _request_view(req: dict[str, Any], student: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "id": str(req["_id"]),
        "student_id": str(req["student_id"]),
        "changes": jsonable(req["changes"]),
        "current": jsonable(req.get("current", {})),
        "reason": req["reason"],
        "status": req["status"],
        "decision_reason": req.get("decision_reason"),
        "created_at": req["created_at"].isoformat(),
        "decided_at": req["decided_at"].isoformat() if req.get("decided_at") else None,
    }
    if student:
        result.update(student_name=student["name"], prn=student["prn"])
    return result


def request_change(ctx: AuthContext, body: ChangeRequestIn, ip: str) -> dict[str, Any]:
    student = my_student(ctx)
    data = body.changes.model_dump(exclude_unset=True)
    if not data:
        raise AppError(422, "Say what should be corrected.", field="changes")
    changes = fields_to_doc(ctx, data)
    if "category_id" in changes:
        check_placement({**student, "category_id": changes["category_id"]})
    changes = {k: v for k, v in changes.items() if student.get(k) != v}
    if not changes:
        raise AppError(422, "These details are already on your record.", field="changes")
    db = get_db()
    pending = db.student_change_requests.find({"student_id": student["_id"], "status": "pending"})
    busy = {field for req in pending for field in req["changes"]} & set(changes)
    if busy:
        raise AppError(409, "You already asked to correct this; wait for the office to decide.", "conflict", "changes")
    req = {
        "student_id": student["_id"],
        "changes": changes,
        "current": {k: student.get(k) for k in changes},
        "reason": body.reason.strip(),
        "status": "pending",
        "created_at": datetime.now(UTC),
        "created_by": ctx.user_id,
    }
    req["_id"] = db.student_change_requests.insert_one(req).inserted_id
    audit.record(
        "students.change_requested",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"request_id": str(req["_id"]), "fields": sorted(changes)},
    )
    return _request_view(req)


def correction_options() -> dict[str, Any]:
    rows = get_db().categories.find({"status": "active"}, {"code": 1, "name": 1}).sort("code", ASCENDING)
    return {"categories": [{"id": str(c["_id"]), "code": c["code"], "name": c["name"]} for c in rows]}


def my_requests(ctx: AuthContext) -> list[dict[str, Any]]:
    student = my_student(ctx)
    rows = get_db().student_change_requests.find({"student_id": student["_id"]}).sort("created_at", DESCENDING)
    return [_request_view(r) for r in rows]


def request_queue(status: str | None, student_id: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if student_id:
        query["student_id"] = oid(student_id)
    db = get_db()
    rows = list(db.student_change_requests.find(query).sort("created_at", ASCENDING).limit(500))
    students = {s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}})}
    return [_request_view(r, students.get(r["student_id"])) for r in rows]


def decide_request(ctx: AuthContext, request_id: str, approve: bool, reason: str | None, ip: str) -> dict[str, Any]:
    db = get_db()
    rid = oid(request_id, "Request")
    if not approve and not (reason and reason.strip()):
        raise AppError(422, "Tell the student why the correction was not made.", field="reason")

    def work(session: ClientSession) -> dict[str, Any]:
        req = db.student_change_requests.find_one_and_update(
            {"_id": rid, "status": "pending"},
            {
                "$set": {
                    "status": "approved" if approve else "rejected",
                    "decided_at": datetime.now(UTC),
                    "decided_by": ctx.user_id,
                    "decision_reason": (reason or "").strip() or None,
                }
            },
            session=session,
            return_document=True,
        )
        if not req:
            raise AppError(409, "This request was already decided.", "conflict")
        student = get_student(req["student_id"], session=session)
        if approve:
            merged = {**student, **req["changes"]}
            check_placement(merged)
            apply_changes(
                ctx, student, req["changes"], action="students.change_approved", ip=ip, reason=reason, session=session
            )
        else:
            audit.record(
                "students.change_rejected",
                actor_id=ctx.user_id,
                target_type="student",
                target_id=student["_id"],
                ip=ip,
                reason=reason,
                details={"request_id": str(rid)},
                session=session,
            )
        return _request_view(req, student)

    return run_in_transaction(work)


# --- photo and documents ---------------------------------------------------------------------


def set_photo(ctx: AuthContext, student: dict[str, Any], filename: str, data: bytes, ip: str) -> dict[str, Any]:
    saved = files.save(
        data, filename=filename, student_id=student["_id"], purpose="photo", created_by=ctx.user_id, images_only=True
    )
    get_db().students.update_one(
        {"_id": student["_id"]}, {"$set": {"photo_file_id": saved["_id"], "updated_at": datetime.now(UTC)}}
    )
    audit.record("students.photo_changed", actor_id=ctx.user_id, target_type="student", target_id=student["_id"], ip=ip)
    return view(get_student(student["_id"]))


def add_document(
    ctx: AuthContext, student: dict[str, Any], doc_type: str, filename: str, data: bytes, *, by_office: bool, ip: str
) -> dict[str, Any]:
    saved = files.save(data, filename=filename, student_id=student["_id"], purpose=doc_type, created_by=ctx.user_id)
    now = datetime.now(UTC)
    entry: dict[str, Any] = {
        "id": ObjectId(),
        "type": doc_type,
        "file_id": saved["_id"],
        "filename": saved["filename"],
        # The office checks what it uploads itself; a student's upload waits for verification.
        "status": "verified" if by_office else "pending",
        "uploaded_at": now,
        "uploaded_by": ctx.user_id,
    }
    if by_office:
        entry.update(verified_by=ctx.user_id, verified_at=now)
    get_db().students.update_one({"_id": student["_id"]}, {"$push": {"documents": entry}, "$set": {"updated_at": now}})
    audit.record(
        "students.document_added",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"type": doc_type, "document_id": str(entry["id"])},
    )
    return view(get_student(student["_id"]))


def decide_document(
    ctx: AuthContext, student_id: ObjectId, document_id: str, verified: bool, reason: str | None, ip: str
) -> dict[str, Any]:
    if not verified and not (reason and reason.strip()):
        raise AppError(422, "Give a reason so the student knows what to upload instead.", field="reason")
    did = oid(document_id, "Document")
    result = get_db().students.update_one(
        {"_id": student_id, "documents.id": did},
        {
            "$set": {
                "documents.$.status": "verified" if verified else "rejected",
                "documents.$.reason": (reason or "").strip() or None,
                "documents.$.verified_by": ctx.user_id,
                "documents.$.verified_at": datetime.now(UTC),
            }
        },
    )
    if not result.matched_count:
        raise AppError(404, "Document not found.")
    audit.record(
        "students.document_verified" if verified else "students.document_rejected",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student_id,
        ip=ip,
        reason=reason,
        details={"document_id": document_id},
    )
    return view(get_student(student_id))


def file_for(ctx: AuthContext, file_id: str) -> dict[str, Any]:
    """A stored file, if this user may see it: staff with students.read, or the student it belongs to."""
    doc = files.load(file_id)
    if P.STUDENTS_READ in ctx.permissions:
        return doc
    if ctx.user.get("kind") == "student":
        mine = get_db().students.find_one({"user_id": ctx.user_id}, {"_id": 1})
        if mine and mine["_id"] == doc.get("student_id"):
            return doc
    if (
        ctx.user.get("kind") == "applicant"
        and doc.get("purpose") == "application"
        and doc.get("created_by") == ctx.user_id
    ):
        return doc  # an applicant's own upload
    if ctx.user.get("kind") == "parent":
        child = my_student(ctx)  # parents: only their child's photo
        if doc["_id"] == child.get("photo_file_id"):
            return doc
    raise AppError(404, "File not found.")  # not 403: don't reveal that the file exists
