"""User accounts (staff, students, parents) in the `users` collection."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import ROLE_LABELS, Role, mfa_required, permissions_for

register_indexes(
    "users",
    [
        IndexModel([("email", ASCENDING)], unique=True, partialFilterExpression={"email": {"$type": "string"}}),
        IndexModel([("prn", ASCENDING)], unique=True, partialFilterExpression={"prn": {"$type": "string"}}),
        IndexModel([("phone", ASCENDING)]),
        IndexModel([("roles", ASCENDING)]),
        IndexModel([("kind", ASCENDING), ("name", ASCENDING)]),
    ],
)

KINDS = ("staff", "student", "parent")


def normalize_email(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value or None


def normalize_prn(value: str | None) -> str | None:
    value = (value or "").strip().upper()
    return value or None


def parse_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AppError(404, "User not found.") from e


def find_by_identifier(identifier: str) -> dict[str, Any] | None:
    """Staff sign in with their email; students with their PRN."""
    identifier = identifier.strip()
    if "@" in identifier:
        return get_db().users.find_one({"email": normalize_email(identifier)})
    return get_db().users.find_one({"prn": normalize_prn(identifier)})


def get_user(user_id: ObjectId) -> dict[str, Any]:
    user = get_db().users.find_one({"_id": user_id})
    if not user:
        raise AppError(404, "User not found.")
    return user


def create_user(
    *,
    kind: str,
    name: str,
    roles: list[str],
    password_hash: str,
    must_change_password: bool,
    created_by: ObjectId | None,
    email: str | None = None,
    prn: str | None = None,
    phone: str | None = None,
    session: ClientSession | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        "kind": kind,
        "name": name.strip(),
        "roles": roles,
        "status": "active",
        "password_hash": password_hash,
        "must_change_password": must_change_password,
        "password_changed_at": now,
        "failed_logins": 0,
        "locked_until": None,
        "mfa": {"enabled": False},
        "created_at": now,
        "created_by": created_by,
        "updated_at": now,
    }
    if email:
        doc["email"] = normalize_email(email)
    if prn:
        doc["prn"] = normalize_prn(prn)
    if phone:
        doc["phone"] = phone.strip()
    try:
        result = get_db().users.insert_one(doc, session=session)
    except DuplicateKeyError as e:
        field = "email" if "email" in str(e) else "prn"
        label = "email" if field == "email" else "PRN"
        raise AppError(409, f"Another account already uses this {label}.", field=field) from e
    doc["_id"] = result.inserted_id
    return doc


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """What the API returns about an account (never hashes or secrets)."""
    roles = user.get("roles", [])
    locked_until = user.get("locked_until")
    return {
        "id": str(user["_id"]),
        "kind": user["kind"],
        "name": user["name"],
        "email": user.get("email"),
        "prn": user.get("prn"),
        "phone": user.get("phone"),
        "roles": roles,
        "role_labels": [ROLE_LABELS[Role(r)] for r in roles if r in Role.__members__.values()],
        "status": user.get("status", "active"),
        "must_change_password": bool(user.get("must_change_password")),
        "mfa_enabled": bool(user.get("mfa", {}).get("enabled")),
        "mfa_required": mfa_required(roles),
        "locked": bool(locked_until and locked_until > datetime.now(UTC)),
        "last_login_at": user["last_login_at"].isoformat() if user.get("last_login_at") else None,
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
    }


def me_payload(user: dict[str, Any], session_state: str) -> dict[str, Any]:
    return {
        **public_user(user),
        "permissions": sorted(permissions_for(user.get("roles", []))),
        "session_state": session_state,
    }
