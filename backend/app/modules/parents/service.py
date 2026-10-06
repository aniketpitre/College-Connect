"""
Parents and guardians (spec R14, plan 3.1).

A parent account is found by its mobile number and linked to one or more students by the
office. Parents sign in with their mobile number and a one-time code (sent to the email on
record; SMS comes with the messaging service), or with a password they set through
"Forgot password". They see their child's pages read-only, through the same `/me/*` endpoints
the student uses, with the child chosen by the `X-Child` header (see `guard.py`).

Consent (DPDP Act): a student aged 18 or over decides whether parents see fees, attendance and
marks/results (all on by default). For a student under 18 the parent sees everything, and the
office must record the parent's consent when linking.
"""

import hmac
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import Request, Response
from pymongo import ASCENDING, IndexModel

from app.core import audit, clock
from app.core.auth import AuthContext, create_session, revoke_user_sessions
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.requestinfo import client_ip
from app.core.security import token_hash
from app.modules.parents.schemas import Access, ParentLink
from app.modules.students import service as students
from app.modules.users import repo as users_repo

register_indexes(
    "users",
    [IndexModel([("children.student_id", ASCENDING)], partialFilterExpression={"kind": "parent"})],
)
register_indexes("login_codes", [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)])

AREAS = ("fees", "attendance", "results")
DEFAULT_ACCESS = dict.fromkeys(AREAS, True)
CODE_LIFETIME = timedelta(minutes=10)
CODE_ATTEMPTS = 5
NOT_SHARED = "Your child has not shared this with parents."


# --- age and consent ------------------------------------------------------------------------


def age(student: dict[str, Any]) -> int | None:
    dob = student.get("dob")
    if not dob:
        return None
    born = date.fromisoformat(str(dob)[:10])
    today = clock.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def is_minor(student: dict[str, Any]) -> bool:
    years = age(student)
    return years is not None and years < 18


def access(student: dict[str, Any]) -> dict[str, bool]:
    """What parents may see. Under-18s can't restrict it; an unknown birth date counts as adult."""
    if is_minor(student):
        return dict(DEFAULT_ACCESS)
    return {**DEFAULT_ACCESS, **{k: bool(v) for k, v in (student.get("parent_access") or {}).items() if k in AREAS}}


# --- the office links parents ---------------------------------------------------------------


def _parent_view(user: dict[str, Any], student_id: ObjectId | None = None) -> dict[str, Any]:
    link: dict[str, Any] = next((c for c in user.get("children", []) if c["student_id"] == student_id), {})
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "phone": user.get("phone"),
        "email": user.get("contact_email"),
        "relation": link.get("relation"),
        "status": user.get("status", "active"),
        "last_login_at": user["last_login_at"].isoformat() if user.get("last_login_at") else None,
        "children": len(user.get("children", [])),
    }


def parents_of(student_id: ObjectId) -> dict[str, Any]:
    student = students.get_student(student_id)
    rows = get_db().users.find({"kind": "parent", "children.student_id": student_id}).sort("name", 1)
    return {
        "parents": [_parent_view(u, student_id) for u in rows],
        "minor": is_minor(student),
        "consent_recorded": bool((student.get("guardian_consent") or {}).get("recorded")),
        "access": access(student),
    }


def link(ctx: AuthContext, student_id: ObjectId, body: ParentLink, ip: str) -> dict[str, Any]:
    student = students.get_student(student_id)
    consent_recorded = bool((student.get("guardian_consent") or {}).get("recorded"))
    if is_minor(student) and not consent_recorded and not body.consent:
        raise AppError(
            422, "This student is under 18: record the parent's consent to link them.", "consent_required", "consent"
        )
    db = get_db()
    now = datetime.now(UTC)
    existing = db.users.find_one({"phone": body.phone, "kind": {"$ne": "staff"}})
    if existing and existing["kind"] != "parent":
        raise AppError(409, "This mobile number belongs to a student account.", "conflict", "phone")
    if existing and any(c["student_id"] == student_id for c in existing.get("children", [])):
        raise AppError(409, "This parent is already linked to the student.", "conflict", "phone")
    child = {"student_id": student_id, "relation": body.relation.strip(), "linked_at": now, "linked_by": ctx.user_id}

    def work(session) -> ObjectId:
        if existing:
            update: dict[str, Any] = {"status": "active", "updated_at": now}
            if body.email and not existing.get("contact_email"):
                update["contact_email"] = str(body.email).lower()
            db.users.update_one(
                {"_id": existing["_id"]}, {"$set": update, "$push": {"children": child}}, session=session
            )
            parent_id = existing["_id"]
        else:
            user = users_repo.create_user(
                kind="parent",
                name=body.name,
                roles=["parent"],
                password_hash=None,  # parents sign in with a one-time code until they set a password
                must_change_password=False,
                created_by=ctx.user_id,
                phone=body.phone,
                session=session,
            )
            extra: dict[str, Any] = {"children": [child]}
            if body.email:
                extra["contact_email"] = str(body.email).lower()
            db.users.update_one({"_id": user["_id"]}, {"$set": extra}, session=session)
            parent_id = user["_id"]
        if body.consent and not consent_recorded:
            db.students.update_one(
                {"_id": student_id},
                {"$set": {"guardian_consent": {"recorded": True, "by": ctx.user_id, "at": now}}},
                session=session,
            )
        audit.record(
            "parents.linked",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student_id,
            ip=ip,
            details={"parent_id": str(parent_id), "relation": child["relation"], "new_account": not existing},
            session=session,
        )
        return parent_id

    run_in_transaction(work)
    return parents_of(student_id)


def unlink(ctx: AuthContext, student_id: ObjectId, parent_id: str, ip: str) -> dict[str, Any]:
    db = get_db()
    pid = students.oid(parent_id, "Parent")
    parent = db.users.find_one({"_id": pid, "kind": "parent", "children.student_id": student_id})
    if not parent:
        raise AppError(404, "Parent not found.")
    db.users.update_one({"_id": pid}, {"$pull": {"children": {"student_id": student_id}}})
    if len(parent.get("children", [])) <= 1:
        # No children left at the college: the account can't see anything, so it is closed.
        db.users.update_one({"_id": pid}, {"$set": {"status": "disabled"}})
        revoke_user_sessions(pid)
    audit.record(
        "parents.unlinked",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student_id,
        ip=ip,
        details={"parent_id": parent_id},
    )
    return parents_of(student_id)


# --- the parent's own view ------------------------------------------------------------------


def _child_ids(ctx: AuthContext) -> list[ObjectId]:
    return [c["student_id"] for c in ctx.user.get("children", [])]


def children(ctx: AuthContext) -> list[dict[str, Any]]:
    ids = _child_ids(ctx)
    docs = {s["_id"]: s for s in get_db().students.find({"_id": {"$in": ids}})}
    lookups = students._lookups()
    out = []
    for link_ in ctx.user.get("children", []):
        s = docs.get(link_["student_id"])
        if not s:
            continue
        summary = students.summary(s, lookups)
        label = " · ".join(x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x)
        out.append(
            {
                "id": str(s["_id"]),
                "name": s["name"],
                "prn": s.get("prn"),
                "class": label,
                "status": s.get("status"),
                "relation": link_.get("relation"),
                "photo_url": f"/files/{s['photo_file_id']}" if s.get("photo_file_id") else None,
                "access": access(s),
            }
        )
    return out


def child(ctx: AuthContext) -> dict[str, Any]:
    """The student a parent's request is about: the `X-Child` header, or their only child."""
    ids = _child_ids(ctx)
    wanted = ctx.child_id
    if wanted is None and len(ids) != 1:
        raise AppError(400, "Choose which child to see.", "choose_child")
    chosen = ids[0] if wanted is None else next((i for i in ids if str(i) == wanted), None)
    if chosen is None:
        raise AppError(404, "Student not found.")  # not linked: don't reveal anything
    doc = get_db().students.find_one({"_id": chosen})
    if not doc:
        raise AppError(404, "Student not found.")
    return doc


def check_area(ctx: AuthContext, area: str) -> None:
    if not access(child(ctx))[area]:
        raise AppError(403, NOT_SHARED, "not_shared")


# --- the student's consent controls ---------------------------------------------------------


def my_sharing(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    rows = get_db().users.find(
        {"kind": "parent", "status": "active", "children.student_id": student["_id"]}, {"name": 1, "children": 1}
    )
    return {
        "can_change": not is_minor(student),
        "access": access(student),
        "parents": [
            {
                "name": u["name"],
                "relation": next((c.get("relation") for c in u["children"] if c["student_id"] == student["_id"]), None),
            }
            for u in rows
        ],
    }


def set_sharing(ctx: AuthContext, body: Access, ip: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    if is_minor(student):
        raise AppError(409, "Students under 18 can't change what parents see.", "minor")
    new = body.model_dump()
    get_db().students.update_one({"_id": student["_id"]}, {"$set": {"parent_access": new}})
    audit.record(
        "parents.access_changed",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details=new,
    )
    return my_sharing(ctx)


# --- sign in with a one-time code -----------------------------------------------------------


def _code_hash(phone: str, code: str) -> str:
    return token_hash(f"{phone}:{code}")


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'•' * max(1, len(name) - 2)}@{domain}"


def request_code(request: Request, phone: str, kind: str = "parent") -> dict[str, Any]:
    """Parents and admission applicants sign in with a one-time code."""
    ip = client_ip(request)
    hit(f"otp:ip:{ip}", limit=20, window_seconds=60 * 60)
    hit(f"otp:{kind}:{phone}", limit=5, window_seconds=60 * 60)
    db = get_db()
    user = db.users.find_one({"phone": phone, "kind": kind, "status": "active"})
    if user and (user.get("contact_email") or user.get("phone")):
        code = f"{secrets.randbelow(10**6):06d}"
        db.login_codes.replace_one(
            {"_id": f"{kind}:{phone}"},
            {"code_hash": _code_hash(phone, code), "attempts": 0, "expires_at": datetime.now(UTC) + CODE_LIFETIME},
            upsert=True,
        )
        from app.modules.messaging import service as messaging

        messaging.send_to(user, "otp", {"code": code})  # SMS/WhatsApp when set up, and email
        audit.record("auth.otp.sent", actor_id=user["_id"], ip=ip)
    # The same answer whether or not the number is registered, so numbers can't be checked here.
    return {"sent": True}


def verify_code(request: Request, response: Response, phone: str, code: str, kind: str = "parent") -> dict[str, Any]:
    ip = client_ip(request)
    hit(f"otp:verify:ip:{ip}", limit=30, window_seconds=15 * 60)
    db = get_db()
    wrong = AppError(401, "That code is wrong or has expired. Ask for a new one.", "invalid_code", "code")
    key = f"{kind}:{phone}"
    doc = db.login_codes.find_one({"_id": key, "expires_at": {"$gt": datetime.now(UTC)}})
    if not doc or doc["attempts"] >= CODE_ATTEMPTS:
        raise wrong
    if not hmac.compare_digest(doc["code_hash"], _code_hash(phone, code)):
        db.login_codes.update_one({"_id": key}, {"$inc": {"attempts": 1}})
        raise wrong
    db.login_codes.delete_one({"_id": key})
    user = db.users.find_one({"phone": phone, "kind": kind, "status": "active"})
    if not user:
        raise wrong
    now = datetime.now(UTC)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now, "failed_logins": 0}})
    create_session(response, request, user, "active")
    audit.record("auth.login.succeeded", actor_id=user["_id"], ip=ip, details={"state": "active", "method": "otp"})
    return users_repo.me_payload(user, "active")
