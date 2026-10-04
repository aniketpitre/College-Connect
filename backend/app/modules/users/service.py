"""Creating and managing accounts (System Admin for staff; Office for students)."""

import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core import audit
from app.core.auth import AuthContext, revoke_user_sessions
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rbac import ROLE_LABELS, STAFF_ROLES, P, Role, mfa_required
from app.core.security import hash_password, temporary_password
from app.modules.users import repo
from app.modules.users.schemas import UserCreate, UserUpdate


def _can_manage(ctx: AuthContext, target_kind: str) -> bool:
    """Office may manage student accounts; only a System Admin manages staff accounts."""
    perms = ctx.permissions
    if target_kind == "student":
        return P.USERS_CREATE_STUDENT in perms or P.USERS_MANAGE_ROLES in perms
    return P.USERS_MANAGE_ROLES in perms


def _require_manage(ctx: AuthContext, target_kind: str) -> None:
    if not _can_manage(ctx, target_kind):
        raise AppError(403, "You can't manage this kind of account.", "forbidden")


def role_catalog() -> list[dict[str, Any]]:
    return [
        {"id": r.value, "label": ROLE_LABELS[r], "mfa_required": mfa_required([r.value])}
        for r in Role
        if r in STAFF_ROLES
    ]


def list_users(
    ctx: AuthContext, *, search: str | None, kind: str | None, role: str | None, skip: int, limit: int
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if kind:
        query["kind"] = kind
    if role:
        query["roles"] = role
    if search and search.strip():
        pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{"name": pattern}, {"email": pattern}, {"prn": pattern}, {"phone": pattern}]
    db = get_db()
    total = db.users.count_documents(query)
    rows = db.users.find(query).sort([("kind", 1), ("name", 1)]).skip(skip).limit(limit)
    return {"items": [repo.public_user(u) for u in rows], "total": total}


def create(ctx: AuthContext, body: UserCreate, ip: str) -> dict[str, Any]:
    if body.kind == "staff" and P.USERS_CREATE_STAFF not in ctx.permissions:
        raise AppError(403, "Only a System Admin can create staff accounts.", "forbidden")
    if body.kind == "student" and P.USERS_CREATE_STUDENT not in ctx.permissions:
        raise AppError(403, "You can't create student accounts.", "forbidden")
    temp = temporary_password()
    user = repo.create_user(
        kind=body.kind,
        name=body.name,
        email=str(body.email) if body.email else None,
        prn=body.prn,
        phone=body.phone,
        roles=body.roles,
        password_hash=hash_password(temp),
        must_change_password=True,
        created_by=ctx.user_id,
    )
    audit.record(
        "users.created",
        actor_id=ctx.user_id,
        target_type="user",
        target_id=user["_id"],
        ip=ip,
        details={"kind": body.kind, "roles": body.roles},
    )
    return {"user": repo.public_user(user), "temporary_password": temp}


def _active_admins_other_than(user_id: ObjectId) -> int:
    return get_db().users.count_documents(
        {"_id": {"$ne": user_id}, "roles": Role.SYSTEM_ADMIN.value, "status": "active"}
    )


def update(ctx: AuthContext, user_id: ObjectId, body: UserUpdate, ip: str) -> dict[str, Any]:
    target = repo.get_user(user_id)
    _require_manage(ctx, target["kind"])
    changes: dict[str, Any] = {}
    if body.name is not None:
        changes["name"] = body.name.strip()
    if body.email is not None:
        changes["email"] = repo.normalize_email(str(body.email))
    if body.phone is not None:
        changes["phone"] = body.phone.strip()

    if body.roles is not None and sorted(set(body.roles)) != sorted(target.get("roles", [])):
        if target["kind"] != "staff":
            raise AppError(422, "Only staff accounts have editable roles.", field="roles")
        if P.USERS_MANAGE_ROLES not in ctx.permissions:
            raise AppError(403, "Only a System Admin can change roles.", "forbidden")
        roles = sorted(set(body.roles))
        if not roles or any(r not in STAFF_ROLES for r in roles):
            raise AppError(422, "Choose one or more valid staff roles.", field="roles")
        if (
            Role.SYSTEM_ADMIN.value in target.get("roles", [])
            and Role.SYSTEM_ADMIN.value not in roles
            and _active_admins_other_than(user_id) == 0
        ):
            raise AppError(409, "This is the last System Admin; add another admin first.", "last_admin", "roles")
        changes["roles"] = roles

    if body.status is not None and body.status != target.get("status", "active"):
        if user_id == ctx.user_id:
            raise AppError(409, "You can't disable your own account.", "conflict", "status")
        if (
            body.status == "disabled"
            and Role.SYSTEM_ADMIN.value in target.get("roles", [])
            and _active_admins_other_than(user_id) == 0
        ):
            raise AppError(409, "This is the last System Admin; it can't be disabled.", "last_admin", "status")
        changes["status"] = body.status

    if not changes:
        return repo.public_user(target)
    changes["updated_at"] = datetime.now(UTC)
    get_db().users.update_one({"_id": user_id}, {"$set": changes})
    if changes.get("status") == "disabled" or "roles" in changes:
        revoke_user_sessions(user_id)  # take effect immediately
    audit.record(
        "users.updated",
        actor_id=ctx.user_id,
        target_type="user",
        target_id=user_id,
        ip=ip,
        reason=body.reason,
        details={
            "before": {k: target.get(k) for k in changes if k != "updated_at"},
            "after": {k: v for k, v in changes.items() if k != "updated_at"},
        },
    )
    return repo.public_user(repo.get_user(user_id))


def reset_password(ctx: AuthContext, user_id: ObjectId, reason: str | None, ip: str) -> dict[str, Any]:
    target = repo.get_user(user_id)
    needed = P.USERS_RESET_STUDENT if target["kind"] == "student" else P.USERS_RESET_STAFF
    if needed not in ctx.permissions:
        raise AppError(403, "You can't reset this account's password.", "forbidden")
    if user_id == ctx.user_id:
        raise AppError(409, "Use 'Change password' for your own account.", "conflict")
    temp = temporary_password()
    get_db().users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "password_hash": hash_password(temp),
                "must_change_password": True,
                "password_changed_at": datetime.now(UTC),
                "failed_logins": 0,
                "locked_until": None,
            }
        },
    )
    revoke_user_sessions(user_id)
    audit.record(
        "users.password_reset_by_staff",
        actor_id=ctx.user_id,
        target_type="user",
        target_id=user_id,
        ip=ip,
        reason=reason,
    )
    return {"temporary_password": temp}


def unlock(ctx: AuthContext, user_id: ObjectId, ip: str) -> dict[str, Any]:
    target = repo.get_user(user_id)
    _require_manage(ctx, target["kind"])
    get_db().users.update_one({"_id": user_id}, {"$set": {"failed_logins": 0, "locked_until": None}})
    audit.record("users.unlocked", actor_id=ctx.user_id, target_type="user", target_id=user_id, ip=ip)
    return repo.public_user(repo.get_user(user_id))
