"""Sign-in, sign-out, password change and first-admin setup."""

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request, Response

from app.core import audit
from app.core.auth import AuthContext, create_session, end_session, revoke_user_sessions
from app.core.db import get_db
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.rbac import Role, mfa_required
from app.core.requestinfo import client_ip
from app.core.security import hash_password, needs_rehash, validate_new_password, verify_password
from app.modules.users import repo

MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=15)
WRONG_CREDENTIALS = "Wrong email/PRN or password."


def _initial_state(user: dict[str, Any]) -> str:
    if user.get("mfa", {}).get("enabled"):
        return "mfa_pending"
    if mfa_required(user.get("roles", [])):
        return "mfa_setup"
    return "active"


def login(request: Request, response: Response, identifier: str, password: str) -> dict[str, Any]:
    ip = client_ip(request)
    hit(f"login:ip:{ip}", limit=30, window_seconds=15 * 60)
    db = get_db()
    user = repo.find_by_identifier(identifier)

    if user is None:
        verify_password(None, password)  # same work as a real check, so timing doesn't reveal accounts
        audit.record("auth.login.failed", ip=ip, details={"reason": "unknown_account"})
        raise AppError(401, WRONG_CREDENTIALS, "invalid_credentials")

    now = datetime.now(UTC)
    if user.get("locked_until") and user["locked_until"] > now:
        audit.record("auth.login.failed", actor_id=user["_id"], ip=ip, details={"reason": "locked"})
        minutes = max(1, int((user["locked_until"] - now).total_seconds() // 60) + 1)
        raise AppError(429, f"Too many wrong attempts. Try again in {minutes} minutes.", "account_locked")

    if not verify_password(user.get("password_hash"), password):
        failures = user.get("failed_logins", 0) + 1
        update: dict[str, Any] = {"failed_logins": failures}
        if failures >= MAX_FAILED_LOGINS:
            update = {"failed_logins": 0, "locked_until": now + LOCK_DURATION}
            audit.record("auth.account.locked", actor_id=user["_id"], ip=ip)
        db.users.update_one({"_id": user["_id"]}, {"$set": update})
        audit.record("auth.login.failed", actor_id=user["_id"], ip=ip, details={"reason": "wrong_password"})
        raise AppError(401, WRONG_CREDENTIALS, "invalid_credentials")

    if user.get("status") == "disabled":
        audit.record("auth.login.failed", actor_id=user["_id"], ip=ip, details={"reason": "disabled"})
        raise AppError(403, "This account is disabled. Please contact the college office.", "account_disabled")

    update = {"failed_logins": 0, "locked_until": None, "last_login_at": now}
    if needs_rehash(user["password_hash"]):
        update["password_hash"] = hash_password(password)
    db.users.update_one({"_id": user["_id"]}, {"$set": update})
    user.update(update)

    state = _initial_state(user)
    create_session(response, request, user, state)
    audit.record("auth.login.succeeded", actor_id=user["_id"], ip=ip, details={"state": state})
    return repo.me_payload(user, state)


def logout(request: Request, response: Response, ctx: AuthContext | None) -> None:
    if ctx:
        audit.record("auth.logout", actor_id=ctx.user_id, ip=client_ip(request))
    end_session(response, ctx.session if ctx else None)


def logout_everywhere(request: Request, response: Response, ctx: AuthContext) -> int:
    count = revoke_user_sessions(ctx.user_id)
    end_session(response, None)
    audit.record("auth.logout_all", actor_id=ctx.user_id, ip=client_ip(request), details={"sessions": count})
    return count


def change_password(request: Request, response: Response, ctx: AuthContext, current: str, new: str) -> dict:
    user = ctx.user
    hit(f"pwchange:{user['_id']}", limit=10, window_seconds=15 * 60)
    if not verify_password(user.get("password_hash"), current):
        raise AppError(400, "Your current password is wrong.", "invalid_credentials", "current_password")
    if new == current:
        raise AppError(422, "Choose a password different from the current one.", "weak_password", "new_password")
    validate_new_password(new, avoid=(user.get("name"), user.get("email"), user.get("prn")))
    now = datetime.now(UTC)
    get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(new), "must_change_password": False, "password_changed_at": now}},
    )
    # Every other device is signed out; this one gets a fresh session token.
    revoke_user_sessions(user["_id"], keep_session_id=ctx.session["_id"])
    end_session(response, ctx.session)
    user.update(must_change_password=False)
    create_session(response, request, user, "active")
    audit.record("auth.password.changed", actor_id=user["_id"], ip=client_ip(request))
    return repo.me_payload(user, "active")


def setup_status() -> dict[str, bool]:
    token_configured = bool(os.getenv("SETUP_TOKEN"))
    return {"needs_setup": token_configured and get_db().users.estimated_document_count() == 0}


def first_admin_setup(request: Request, name: str, email: str, password: str, setup_token: str) -> dict:
    expected = os.getenv("SETUP_TOKEN")
    hit(f"setup:{client_ip(request)}", limit=10, window_seconds=60 * 60)
    if not expected or not secrets.compare_digest(setup_token.encode(), expected.encode()):
        raise AppError(403, "Invalid setup token.", "forbidden", "setup_token")
    if get_db().users.count_documents({}, limit=1):
        raise AppError(409, "Setup is already complete. Sign in instead.", "already_set_up")
    validate_new_password(password, avoid=(name, email), field="password")
    user = repo.create_user(
        kind="staff",
        name=name,
        email=email,
        roles=[Role.SYSTEM_ADMIN.value],
        password_hash=hash_password(password),
        must_change_password=False,
        created_by=None,
    )
    audit.record(
        "setup.first_admin", actor_id=user["_id"], ip=client_ip(request), target_type="user", target_id=user["_id"]
    )
    return repo.public_user(user)


def my_sessions(ctx: AuthContext) -> list[dict]:
    rows = (
        get_db()
        .sessions.find({"user_id": ctx.user_id, "expires_at": {"$gt": datetime.now(UTC)}})
        .sort("last_seen_at", -1)
    )
    return [
        {
            "id": s["sid"],
            "current": s["_id"] == ctx.session["_id"],
            "created_at": s["created_at"].isoformat(),
            "last_seen_at": s["last_seen_at"].isoformat(),
            "ip": s.get("ip"),
            "user_agent": s.get("user_agent"),
        }
        for s in rows
    ]


def end_my_session(request: Request, ctx: AuthContext, sid: str) -> None:
    deleted = get_db().sessions.delete_one({"user_id": ctx.user_id, "sid": sid}).deleted_count
    if not deleted:
        raise AppError(404, "Session not found.")
    audit.record("auth.session.ended", actor_id=ctx.user_id, ip=client_ip(request))


def login_history(ctx: AuthContext, limit: int = 20) -> list[dict]:
    rows = (
        get_db().audit_log.find({"actor_id": ctx.user_id, "action": {"$regex": "^auth\\."}}).sort("at", -1).limit(limit)
    )
    return [
        {
            "at": r["at"].isoformat(),
            "action": r["action"],
            "ip": r.get("ip"),
            "reason": (r.get("details") or {}).get("reason"),
        }
        for r in rows
    ]
