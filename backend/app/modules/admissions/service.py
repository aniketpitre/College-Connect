"""
Admissions, part 1 (spec §3.2, R5; plan 3.4): admission cycles, enquiries, the online
application with documents and the application fee, and scrutiny by the Admission Cell.

An applicant has no ERP account: they start an application with their name, mobile number and
email, and sign in with a one-time code (the same mechanism as parents). Their account
(`kind: applicant`) can only reach their own application (see `guard.py`).

Application status: draft → submitted → verified (ready for the merit list), or returned (the
applicant fixes and submits again) or rejected. Merit rounds, confirmation and cancellation are
in `merit.py`.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import Request, Response
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.client_session import ClientSession

from app.core import audit, clock, files
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.requestinfo import client_ip
from app.modules.admissions.schemas import (
    ApplicationIn,
    CycleIn,
    CycleUpdate,
    EnquiryIn,
    EnquiryUpdate,
    StaffEnquiryIn,
    StartIn,
)
from app.modules.students import service as students
from app.modules.users import repo as users_repo

register_indexes(
    "applications",
    [
        IndexModel([("cycle_id", ASCENDING), ("user_id", ASCENDING)], unique=True),
        IndexModel([("cycle_id", ASCENDING), ("programme_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("number", ASCENDING)], unique=True, partialFilterExpression={"number": {"$type": "string"}}),
    ],
)
register_indexes("enquiries", [IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])])

STATUS_LABELS = {
    "draft": "Not submitted yet",
    "submitted": "Submitted, being checked",
    "returned": "Returned: please correct",
    "verified": "Verified, waiting for the merit list",
    "rejected": "Not accepted",
    "offered": "Admission offered",
    "waiting": "On the waiting list",
    "lapsed": "Offer lapsed",
    "admitted": "Admitted",
    "cancelled": "Admission cancelled",
}
EDITABLE = ("draft", "returned")


def oid(value: Any, what: str) -> ObjectId:
    return students.oid(value, what)


# --- admission cycles -----------------------------------------------------------------------


def _check_cycle(body: CycleIn) -> dict[str, Any]:
    db = get_db()
    year = db.academic_years.find_one({"_id": oid(body.academic_year_id, "Academic year")})
    if not year:
        raise AppError(422, "Academic year not found.", field="academic_year_id")
    programmes = []
    for p in body.programmes:
        prog = db.programmes.find_one({"_id": oid(p.programme_id, "Programme"), "status": "active"})
        if not prog:
            raise AppError(422, "Programme not found.", field="programmes")
        reserved = {}
        for cat, n in p.reserved.items():
            if not db.categories.find_one({"_id": oid(cat, "Category"), "status": "active"}):
                raise AppError(422, "Category not found.", field="programmes")
            if n:
                reserved[cat] = n
        programmes.append(
            {"programme_id": prog["_id"], "year_of_study": p.year_of_study, "seats": p.seats, "reserved": reserved}
        )
    if len({p["programme_id"] for p in programmes}) != len(programmes):
        raise AppError(422, "List each programme once.", field="programmes")
    return {
        "name": body.name.strip(),
        "academic_year_id": year["_id"],
        "apply_until": body.apply_until.isoformat(),
        "course_start": body.course_start.isoformat(),
        "application_fee": body.application_fee,
        "programmes": programmes,
        "documents": list(dict.fromkeys(body.documents)),
        "refund_rules": sorted((r.model_dump() for r in body.refund_rules), key=lambda r: -r["days_before"]),
        "processing_fee": body.processing_fee,
    }


def cycle_view(c: dict[str, Any], *, public: bool = False) -> dict[str, Any]:
    db = get_db()
    progs = {p["_id"]: p for p in db.programmes.find({"_id": {"$in": [x["programme_id"] for x in c["programmes"]]}})}
    cats = {str(x["_id"]): x for x in db.categories.find({})}
    out = {
        "id": str(c["_id"]),
        "name": c["name"],
        "status": c["status"],
        "academic_year_id": str(c["academic_year_id"]),
        "apply_until": c["apply_until"],
        "course_start": c["course_start"],
        "application_fee": c["application_fee"],
        "documents": c["documents"],
        "open_now": c["status"] == "open" and clock.today().isoformat() <= c["apply_until"],
        "programmes": [
            {
                "programme_id": str(p["programme_id"]),
                "code": progs.get(p["programme_id"], {}).get("code"),
                "name": progs.get(p["programme_id"], {}).get("name"),
                "year_of_study": p["year_of_study"],
                "seats": p["seats"],
                "reserved": [
                    {"category_id": k, "code": cats.get(k, {}).get("code"), "seats": n}
                    for k, n in p["reserved"].items()
                ],
            }
            for p in c["programmes"]
        ],
    }
    if not public:
        out.update(refund_rules=c["refund_rules"], processing_fee=c["processing_fee"])
    return out


def list_cycles() -> list[dict[str, Any]]:
    return [cycle_view(c) for c in get_db().admission_cycles.find({}).sort("created_at", DESCENDING)]


def create_cycle(ctx: AuthContext, body: CycleIn, ip: str) -> dict[str, Any]:
    doc = {**_check_cycle(body), "status": "draft", "created_at": datetime.now(UTC), "created_by": ctx.user_id}
    doc["_id"] = get_db().admission_cycles.insert_one(doc).inserted_id
    audit.record(
        "admissions.cycle_created", actor_id=ctx.user_id, target_type="admission_cycle", target_id=doc["_id"], ip=ip
    )
    return cycle_view(doc)


def get_cycle(cycle_id: Any) -> dict[str, Any]:
    c = get_db().admission_cycles.find_one(
        {"_id": cycle_id if isinstance(cycle_id, ObjectId) else oid(cycle_id, "Admission")}
    )
    if not c:
        raise AppError(404, "Admission cycle not found.")
    return c


def update_cycle(ctx: AuthContext, cycle_id: str, body: CycleUpdate, ip: str) -> dict[str, Any]:
    c = get_cycle(cycle_id)
    fields = {**_check_cycle(body), "status": body.status}
    used = get_db().applications.distinct("programme_id", {"cycle_id": c["_id"], "status": {"$ne": "draft"}})
    if set(used) - {p["programme_id"] for p in fields["programmes"]}:
        raise AppError(409, "A programme with applications can't be removed from the cycle.", "conflict", "programmes")
    get_db().admission_cycles.update_one({"_id": c["_id"]}, {"$set": fields})
    audit.record(
        "admissions.cycle_updated", actor_id=ctx.user_id, target_type="admission_cycle", target_id=c["_id"], ip=ip,
        details={"status": body.status},
    )  # fmt: skip
    return cycle_view(get_cycle(c["_id"]))


def options() -> dict[str, Any]:
    """Public: what can be applied for now, the categories and whether online payment works."""
    from app.modules.payments import gateway

    db = get_db()
    cycles = [cycle_view(c, public=True) for c in db.admission_cycles.find({"status": "open"})]
    return {
        "cycles": [c for c in cycles if c["open_now"]],
        "categories": [
            {"id": str(c["_id"]), "code": c["code"], "name": c["name"]}
            for c in db.categories.find({"status": "active"}).sort("code", 1)
        ],
        "online_payment": gateway.enabled(),
    }


# --- enquiries ------------------------------------------------------------------------------


def _enquiry_view(e: dict[str, Any]) -> dict[str, Any]:
    prog = get_db().programmes.find_one({"_id": e.get("programme_id")}, {"code": 1}) if e.get("programme_id") else None
    return {
        "id": str(e["_id"]),
        "name": e["name"],
        "phone": e["phone"],
        "email": e.get("email"),
        "programme": prog["code"] if prog else None,
        "message": e.get("message", ""),
        "source": e["source"],
        "status": e["status"],
        "follow_up_on": e.get("follow_up_on"),
        "notes": [{"at": n["at"].isoformat(), "by": n["by_name"], "text": n["text"]} for n in e.get("notes", [])],
        "created_at": e["created_at"].isoformat(),
    }


def _enquiry_doc(body: EnquiryIn, source: str) -> dict[str, Any]:
    prog = None
    if body.programme_id:
        prog = get_db().programmes.find_one({"_id": oid(body.programme_id, "Programme")}, {"_id": 1})
    return {
        "name": body.name.strip(),
        "phone": body.phone,
        "email": str(body.email).lower() if body.email else None,
        "programme_id": prog["_id"] if prog else None,
        "message": body.message.strip(),
        "source": source,
        "status": "new",
        "notes": [],
        "created_at": datetime.now(UTC),
    }


def public_enquiry(request: Request, body: EnquiryIn) -> dict[str, Any]:
    hit(f"enquiry:{client_ip(request)}", limit=5, window_seconds=60 * 60)
    get_db().enquiries.insert_one(_enquiry_doc(body, "website"))
    return {"ok": True}


def add_enquiry(ctx: AuthContext, body: StaffEnquiryIn) -> dict[str, Any]:
    doc = _enquiry_doc(body, body.source)
    doc["follow_up_on"] = body.follow_up_on.isoformat() if body.follow_up_on else None
    doc["created_by"] = ctx.user_id
    doc["_id"] = get_db().enquiries.insert_one(doc).inserted_id
    return _enquiry_view(doc)


def list_enquiries(status: str | None, q: str | None) -> list[dict[str, Any]]:
    import re

    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"name": rx}, {"phone": rx}]
    return [_enquiry_view(e) for e in get_db().enquiries.find(query).sort("created_at", DESCENDING).limit(300)]


def update_enquiry(ctx: AuthContext, enquiry_id: str, body: EnquiryUpdate) -> dict[str, Any]:
    db = get_db()
    e = db.enquiries.find_one({"_id": oid(enquiry_id, "Enquiry")})
    if not e:
        raise AppError(404, "Enquiry not found.")
    update: dict[str, Any] = {"$set": {}}
    if body.status:
        update["$set"]["status"] = body.status
    if "follow_up_on" in body.model_fields_set:
        update["$set"]["follow_up_on"] = body.follow_up_on.isoformat() if body.follow_up_on else None
    if body.note.strip():
        update["$push"] = {
            "notes": {
                "at": datetime.now(UTC),
                "by": ctx.user_id,
                "by_name": ctx.user["name"],
                "text": body.note.strip(),
            }
        }
    if not update["$set"]:
        del update["$set"]
    if len(update):
        db.enquiries.update_one({"_id": e["_id"]}, update)
    return _enquiry_view(db.enquiries.find_one({"_id": e["_id"]}) or e)


# --- applicants sign in ---------------------------------------------------------------------


def start(request: Request, body: StartIn) -> dict[str, Any]:
    """Creates the applicant account and a draft application (or finds them), then sends a code."""
    from app.modules.parents import service as otp

    hit(f"apply:{client_ip(request)}", limit=10, window_seconds=60 * 60)
    cycle = get_cycle(body.cycle_id)
    if cycle["status"] != "open" or clock.today().isoformat() > cycle["apply_until"]:
        raise AppError(409, "Applications for this admission are closed.", "closed")
    db = get_db()
    assert body.phone
    user = db.users.find_one({"phone": body.phone, "kind": "applicant"})
    if user is None:
        user = users_repo.create_user(
            kind="applicant", name=body.name, roles=["applicant"], password_hash=None, must_change_password=False,
            created_by=None, phone=body.phone,
        )  # fmt: skip
        db.users.update_one({"_id": user["_id"]}, {"$set": {"contact_email": str(body.email).lower()}})
    if not db.applications.find_one({"cycle_id": cycle["_id"], "user_id": user["_id"]}):
        now = datetime.now(UTC)
        db.applications.insert_one(
            {
                "cycle_id": cycle["_id"],
                "user_id": user["_id"],
                "status": "draft",
                "personal": {"name": body.name.strip(), "phone": body.phone, "email": str(body.email).lower()},
                "year_of_study": 1,
                "documents": [],
                "fee": {
                    "status": "unpaid" if cycle["application_fee"] else "not_needed",
                    "amount": cycle["application_fee"],
                },
                "created_at": now,
                "updated_at": now,
            }
        )
    return otp.request_code(request, body.phone, kind="applicant")


def request_code(request: Request, phone: str) -> dict[str, Any]:
    from app.modules.parents import service as otp

    return otp.request_code(request, phone, kind="applicant")


def verify_code(request: Request, response: Response, phone: str, code: str) -> dict[str, Any]:
    from app.modules.parents import service as otp

    return otp.verify_code(request, response, phone, code, kind="applicant")


# --- the application ------------------------------------------------------------------------


def view(a: dict[str, Any], *, staff: bool = False) -> dict[str, Any]:
    db = get_db()
    cycle = db.admission_cycles.find_one({"_id": a["cycle_id"]}) or {}
    prog = (
        db.programmes.find_one({"_id": a.get("programme_id")}, {"code": 1, "name": 1})
        if a.get("programme_id")
        else None
    )
    cat = (
        db.categories.find_one({"_id": a["personal"].get("category_id")}) if a["personal"].get("category_id") else None
    )
    p = dict(a["personal"])
    if p.get("category_id"):
        p["category_id"] = str(p["category_id"])
    out = {
        "id": str(a["_id"]),
        "number": a.get("number"),
        "cycle_id": str(a["cycle_id"]),
        "cycle_name": cycle.get("name"),
        "apply_until": cycle.get("apply_until"),
        "status": a["status"],
        "status_label": STATUS_LABELS[a["status"]],
        "can_edit": a["status"] in EDITABLE and clock.today().isoformat() <= cycle.get("apply_until", ""),
        "personal": p,
        "programme_id": str(a["programme_id"]) if a.get("programme_id") else None,
        "programme": f"{prog['code']} · {prog['name']}" if prog else None,
        "programme_code": prog["code"] if prog else None,
        "year_of_study": a.get("year_of_study", 1),
        "category": cat["code"] if cat else None,
        "merit_score": a.get("merit_score"),
        "required_documents": cycle.get("documents", []),
        "documents": [
            {
                "id": str(d["id"]),
                "type": d["type"],
                "filename": d["filename"],
                "status": d["status"],
                "reason": d.get("reason"),
                "url": f"/files/{d['file_id']}",
            }
            for d in a.get("documents", [])
        ],
        "fee": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in a["fee"].items() if k != "by"},
        "reason": a.get("reason"),
        "offer": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in (a.get("offer") or {}).items()}
        or None,
        "rank": a.get("rank"),
        "prn": a.get("prn"),
        "submitted_at": a["submitted_at"].isoformat() if a.get("submitted_at") else None,
    }
    if staff:
        out["student_id"] = str(a["student_id"]) if a.get("student_id") else None
        out["user_id"] = str(a["user_id"])
    return out


def _mine(ctx: AuthContext) -> dict[str, Any]:
    a = get_db().applications.find_one({"user_id": ctx.user_id}, sort=[("created_at", DESCENDING)])
    if not a:
        raise AppError(404, "No application yet.", "no_application")
    return a


def my_application(ctx: AuthContext) -> dict[str, Any]:
    return view(_mine(ctx))


def _editable(a: dict[str, Any]) -> dict[str, Any]:
    cycle = get_cycle(a["cycle_id"])
    if a["status"] not in EDITABLE:
        raise AppError(409, "This application can't be changed now.", "locked")
    if clock.today().isoformat() > cycle["apply_until"]:
        raise AppError(409, "The last date for applications has passed.", "closed")
    return cycle


def save(ctx: AuthContext, body: ApplicationIn) -> dict[str, Any]:
    a = _mine(ctx)
    cycle = _editable(a)
    data = body.model_dump(exclude_unset=True)
    personal = dict(a["personal"])
    update: dict[str, Any] = {}
    if "programme_id" in data:
        pid = oid(data.pop("programme_id"), "Programme") if body.programme_id else None
        if pid and pid not in {p["programme_id"] for p in cycle["programmes"]}:
            raise AppError(422, "Choose a programme from this admission.", field="programme_id")
        update["programme_id"] = pid
        if pid:
            update["year_of_study"] = next(p["year_of_study"] for p in cycle["programmes"] if p["programme_id"] == pid)
    data.pop("year_of_study", None)
    for key, value in students.fields_to_doc(ctx, data).items():
        personal[key] = value
    if personal.get("category_id") and not get_db().categories.find_one(
        {"_id": personal["category_id"], "status": "active"}
    ):
        raise AppError(422, "Category not found.", field="category_id")
    update["personal"] = personal
    update["merit_score"] = (personal.get("previous_education") or {}).get("percentage")
    update["updated_at"] = datetime.now(UTC)
    get_db().applications.update_one({"_id": a["_id"]}, {"$set": update})
    return my_application(ctx)


def add_document(ctx: AuthContext, doc_type: str, filename: str, data: bytes) -> dict[str, Any]:
    a = _mine(ctx)
    _editable(a)
    saved = files.save(data, filename=filename, student_id=None, purpose="application", created_by=ctx.user_id)
    entry = {
        "id": ObjectId(),
        "type": doc_type,
        "file_id": saved["_id"],
        "filename": saved["filename"],
        "status": "pending",
    }
    db = get_db()
    # One file per document type: a new upload replaces the old one.
    old = [d for d in a.get("documents", []) if d["type"] == doc_type]
    db.applications.update_one(
        {"_id": a["_id"]},
        {
            "$set": {
                "documents": [d for d in a.get("documents", []) if d["type"] != doc_type] + [entry],
                "updated_at": datetime.now(UTC),
            }
        },
    )
    for d in old:
        db.files.delete_one({"_id": d["file_id"]})
    return my_application(ctx)


def remove_document(ctx: AuthContext, document_id: str) -> dict[str, Any]:
    a = _mine(ctx)
    _editable(a)
    doc = next((d for d in a.get("documents", []) if str(d["id"]) == document_id), None)
    if not doc:
        raise AppError(404, "Document not found.")
    db = get_db()
    db.applications.update_one({"_id": a["_id"]}, {"$pull": {"documents": {"id": doc["id"]}}})
    db.files.delete_one({"_id": doc["file_id"]})
    return my_application(ctx)


def missing(a: dict[str, Any], cycle: dict[str, Any]) -> list[str]:
    """What the applicant still has to give before submitting."""
    p = a["personal"]
    gaps = [f for f in ("name", "dob", "gender", "phone", "email", "category_id") if not p.get(f)]
    if not a.get("programme_id"):
        gaps.append("programme_id")
    if (p.get("previous_education") or {}).get("percentage") is None:
        gaps.append("previous_education")
    have = {d["type"] for d in a.get("documents", [])}
    gaps += [f"document:{t}" for t in cycle["documents"] if t not in have]
    if a["fee"]["status"] == "unpaid":
        gaps.append("fee")
    return gaps


def submit(ctx: AuthContext, ip: str) -> dict[str, Any]:
    a = _mine(ctx)
    cycle = _editable(a)
    gaps = missing(a, cycle)
    if gaps:
        raise AppError(422, "Fill in everything and upload the documents first.", "incomplete", ",".join(gaps))
    db = get_db()
    year = db.academic_years.find_one({"_id": cycle["academic_year_id"]}) or {"name": "-"}

    def work(session: ClientSession) -> None:
        number = a.get("number")
        if not number:  # numbered once, at the first submission
            counter = db.counters.find_one_and_update(
                {"_id": f"application:{cycle['_id']}"}, {"$inc": {"seq": 1}}, upsert=True,
                return_document=ReturnDocument.AFTER, session=session,
            )  # fmt: skip
            assert counter is not None
            number = f"A/{year['name']}/{counter['seq']:05d}"
        now = datetime.now(UTC)
        db.applications.update_one(
            {"_id": a["_id"]},
            {"$set": {"status": "submitted", "number": number, "submitted_at": now, "updated_at": now, "reason": None}},
            session=session,
        )
        audit.record(
            "admissions.submitted",
            actor_id=ctx.user_id,
            target_type="application",
            target_id=a["_id"],
            ip=ip,
            session=session,
        )

    run_in_transaction(work)
    return my_application(ctx)


# --- application fee ------------------------------------------------------------------------


def record_fee(
    application_id: ObjectId, *, mode: str, reference: str, by: ObjectId | None, session: ClientSession
) -> str | None:
    """Marks the fee paid with the next number in the cycle's application-fee series (inside a transaction)."""
    db = get_db()
    a = db.applications.find_one({"_id": application_id}, session=session)
    assert a is not None
    if a["fee"]["status"] in ("paid", "waived"):
        return a["fee"].get("receipt_number")
    cycle = db.admission_cycles.find_one({"_id": a["cycle_id"]}, session=session)
    assert cycle is not None
    year = db.academic_years.find_one({"_id": cycle["academic_year_id"]}, session=session) or {"name": "-"}
    number = None
    if mode != "waived":
        counter = db.counters.find_one_and_update(
            {"_id": f"application_fee:{year['name']}"}, {"$inc": {"seq": 1}}, upsert=True,
            return_document=ReturnDocument.AFTER, session=session,
        )  # fmt: skip
        assert counter is not None
        number = f"APP/{year['name']}/{counter['seq']:05d}"
    fee = {
        **a["fee"],
        "status": "waived" if mode == "waived" else "paid",
        "mode": mode,
        "reference": reference,
        "receipt_number": number,
        "paid_at": datetime.now(UTC),
        "by": by,
    }
    db.applications.update_one({"_id": a["_id"]}, {"$set": {"fee": fee}}, session=session)
    audit.record(
        "admissions.fee_paid", actor_id=by, target_type="application", target_id=a["_id"], session=session,
        details={"receipt": number, "amount": a["fee"]["amount"], "mode": mode},
    )  # fmt: skip
    return number


def fee_at_counter(ctx: AuthContext, application_id: str, mode: str, reference: str) -> dict[str, Any]:
    a = get_application(application_id)
    if a["fee"]["status"] in ("paid", "waived", "not_needed"):
        raise AppError(409, "The fee is already settled.", "conflict")
    if mode not in ("cash", "waived") and not reference.strip():
        raise AppError(422, "Enter the payment reference.", field="reference")
    run_in_transaction(
        lambda s: record_fee(a["_id"], mode=mode, reference=reference.strip(), by=ctx.user_id, session=s)
    )
    return view(get_application(application_id), staff=True)


def start_fee(ctx: AuthContext) -> dict[str, Any]:
    from app.modules.payments import service as payments

    a = _mine(ctx)
    if a["fee"]["status"] != "unpaid":
        raise AppError(409, "The application fee is already settled.", "conflict")
    return payments.start_application_fee(ctx, a)


def confirm_fee(ctx: AuthContext, payment_id: str, gateway_payment_id: str, signature: str, ip: str) -> dict[str, Any]:
    from app.modules.payments import service as payments

    a = _mine(ctx)
    payments.confirm_application_fee(a, payment_id, gateway_payment_id, signature, ip)
    return my_application(ctx)


# --- scrutiny (Admission Cell) --------------------------------------------------------------


def get_application(application_id: str) -> dict[str, Any]:
    a = get_db().applications.find_one({"_id": oid(application_id, "Application")})
    if not a:
        raise AppError(404, "Application not found.")
    return a


def list_applications(
    *, cycle_id: str | None, programme_id: str | None, status: str | None, q: str | None
) -> list[dict[str, Any]]:
    import re

    db = get_db()
    query: dict[str, Any] = {"status": {"$ne": "draft"}}
    if cycle_id:
        query["cycle_id"] = oid(cycle_id, "Admission")
    if programme_id:
        query["programme_id"] = oid(programme_id, "Programme")
    if status:
        query["status"] = status
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"personal.name": rx}, {"number": rx}, {"personal.phone": rx}]
    rows = db.applications.find(query).sort([("merit_score", DESCENDING), ("submitted_at", ASCENDING)]).limit(1000)
    progs = {p["_id"]: p["code"] for p in db.programmes.find({}, {"code": 1})}
    cats = {c["_id"]: c["code"] for c in db.categories.find({}, {"code": 1})}
    return [
        {
            "id": str(a["_id"]),
            "number": a.get("number"),
            "name": a["personal"].get("name"),
            "phone": a["personal"].get("phone"),
            "programme": progs.get(a.get("programme_id")),
            "category": cats.get(a["personal"].get("category_id")),
            "merit_score": a.get("merit_score"),
            "status": a["status"],
            "status_label": STATUS_LABELS[a["status"]],
            "fee": a["fee"]["status"],
            "documents_pending": sum(1 for d in a.get("documents", []) if d["status"] == "pending"),
            "rank": a.get("rank"),
            "submitted_at": a["submitted_at"].isoformat() if a.get("submitted_at") else None,
        }
        for a in rows
    ]


def decide_document(
    ctx: AuthContext, application_id: str, document_id: str, approve: bool, reason: str | None
) -> dict[str, Any]:
    a = get_application(application_id)
    if a["status"] not in ("submitted", "returned"):
        raise AppError(409, "Documents are checked while the application is being scrutinised.", "conflict")
    if not approve and not (reason or "").strip():
        raise AppError(422, "Say what is wrong with the document.", field="reason")
    docs = a.get("documents", [])
    doc = next((d for d in docs if str(d["id"]) == document_id), None)
    if not doc:
        raise AppError(404, "Document not found.")
    doc.update(
        status="verified" if approve else "rejected",
        reason=None if approve else (reason or "").strip(),
        checked_by=ctx.user_id,
    )
    get_db().applications.update_one({"_id": a["_id"]}, {"$set": {"documents": docs}})
    return view(get_application(application_id), staff=True)


def decide(ctx: AuthContext, application_id: str, action: str, reason: str | None, ip: str) -> dict[str, Any]:
    from app.modules.messaging import service as messaging

    a = get_application(application_id)
    if a["status"] != "submitted":
        raise AppError(409, "Only a submitted application can be decided.", "conflict")
    if action == "verify":
        if any(d["status"] != "verified" for d in a.get("documents", [])):
            raise AppError(409, "Verify every document first.", "documents_pending")
        if a["fee"]["status"] == "unpaid":
            raise AppError(409, "The application fee isn't paid.", "fee_unpaid")
    status = {"verify": "verified", "return": "returned", "reject": "rejected"}[action]
    get_db().applications.update_one(
        {"_id": a["_id"]},
        {
            "$set": {
                "status": status,
                "reason": (reason or "").strip() or None,
                "decided_by": ctx.user_id,
                "decided_at": datetime.now(UTC),
            }
        },
    )
    audit.record(
        f"admissions.{status}",
        actor_id=ctx.user_id,
        target_type="application",
        target_id=a["_id"],
        ip=ip,
        reason=reason,
    )
    if action == "return":
        user = get_db().users.find_one({"_id": a["user_id"]})
        if user:
            messaging.send_to(
                user, "application_returned", {"student": a["personal"]["name"], "reason": (reason or "").strip()}
            )
    return view(get_application(application_id), staff=True)
