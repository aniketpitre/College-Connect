"""
Self-service password reset by email.

The emailed link carries a random token; only its SHA-256 hash is stored. A token works once,
for 30 minutes. Asking for a reset never reveals whether an account exists. Students without
an email address on record ask the college office, which issues a temporary password.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from pymongo import IndexModel

from app.core import audit
from app.core.auth import revoke_user_sessions
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.requestinfo import base_url, client_ip
from app.core.security import hash_password, new_token, token_hash, validate_new_password
from app.modules.users import repo

RESET_LIFETIME = timedelta(minutes=30)
INVALID_LINK = "This reset link is invalid or has expired. Ask for a new one."

register_indexes(
    "password_resets",
    [IndexModel([("expires_at", 1)], expireAfterSeconds=0), IndexModel([("user_id", 1)])],
)


def request_reset(request: Request, identifier: str) -> dict[str, Any]:
    ip = client_ip(request)
    hit(f"reset:ip:{ip}", limit=10, window_seconds=15 * 60)
    hit(f"reset:id:{identifier.strip().lower()}", limit=3, window_seconds=60 * 60)
    user = repo.find_by_identifier(identifier)
    to = (user.get("email") or user.get("contact_email")) if user else None  # parents: their contact email
    if user and user.get("status") != "disabled" and to:
        db = get_db()
        token = new_token()
        now = datetime.now(UTC)
        db.password_resets.delete_many({"user_id": user["_id"]})  # only the newest link works
        db.password_resets.insert_one(
            {
                "_id": token_hash(token),
                "user_id": user["_id"],
                "created_at": now,
                "expires_at": now + RESET_LIFETIME,
                "ip": ip,
            }
        )
        link = f"{base_url(request)}/reset-password#{token}"
        send_email(
            to,
            "Reset your CollegeConnect password",
            f"Hello {user['name']},\n\n"
            "Someone (hopefully you) asked to reset your CollegeConnect password.\n"
            "Open this link within 30 minutes:\n\n"
            f"{link}\n\n"
            "If you didn't ask for this, you can ignore this email; your password stays the same.\n",
        )
        audit.record("auth.password.reset_requested", actor_id=user["_id"], ip=ip)
    return {"ok": True}


def complete_reset(request: Request, token: str, new_password: str) -> dict[str, Any]:
    ip = client_ip(request)
    hit(f"reset:complete:{ip}", limit=20, window_seconds=15 * 60)
    db = get_db()
    now = datetime.now(UTC)
    key = token_hash(token)
    pending = db.password_resets.find_one({"_id": key, "expires_at": {"$gt": now}})
    user = db.users.find_one({"_id": pending["user_id"]}) if pending else None
    if not pending or not user or user.get("status") == "disabled":
        raise AppError(400, INVALID_LINK, "invalid_token", "token")
    validate_new_password(new_password, avoid=(user.get("name"), user.get("email"), user.get("prn")))
    # Single use: whoever deletes the token first wins.
    if not db.password_resets.find_one_and_delete({"_id": key, "expires_at": {"$gt": now}}):
        raise AppError(400, INVALID_LINK, "invalid_token", "token")
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(new_password),
                "must_change_password": False,
                "password_changed_at": now,
                "failed_logins": 0,
                "locked_until": None,
            }
        },
    )
    revoke_user_sessions(user["_id"])
    audit.record("auth.password.reset_completed", actor_id=user["_id"], ip=ip)
    return {"ok": True}
