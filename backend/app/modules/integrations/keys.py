"""
API keys for the open REST API (spec U12, plan 4.6).

The Principal creates a key for another system (a university portal connector, a library
system, the college website) with only the read scopes it needs, and can revoke it at any time.
The key is shown once; only its hash is stored. Keys expire (a year by default) and are
rate-limited; each one records when it was last used.
"""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Header
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.security import token_hash
from app.modules.students import service as students

register_indexes("api_keys", [IndexModel([("prefix", ASCENDING)], unique=True)])

SCOPES = {
    "setup:read": "College structure: years, departments, programmes, classes, subjects",
    "students:read": "Students: PRN, name, class, status, category, gender, email",
    "fees:read": "Fee balances per student and year",
    "attendance:read": "Attendance percentages per student and subject",
    "results:read": "Published results",
    "timetable:read": "Timetables",
    "notices:read": "Notices for everyone",
}
PER_HOUR = 1000


class KeyIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=80, description="What uses it, e.g. University portal sync")
    scopes: list[str] = Field(..., min_length=1)
    valid_days: int = Field(365, ge=1, le=730)


def _view(k: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    state = "revoked" if k.get("revoked_at") else "expired" if k["expires_at"] <= now else "active"
    return {
        "id": str(k["_id"]),
        "name": k["name"],
        "prefix": k["prefix"],
        "scopes": k["scopes"],
        "created_at": k["created_at"],
        "expires_at": k["expires_at"],
        "last_used_at": k.get("last_used_at"),
        "calls": k.get("calls", 0),
        "state": state,
    }


def list_keys() -> dict[str, Any]:
    rows = get_db().api_keys.find({}).sort("created_at", -1)
    return {"keys": [_view(k) for k in rows], "scopes": SCOPES}


def create(ctx: AuthContext, body: KeyIn, ip: str) -> dict[str, Any]:
    unknown = sorted(set(body.scopes) - set(SCOPES))
    if unknown:
        raise AppError(422, f"Unknown scope: {', '.join(unknown)}.", field="scopes")
    prefix = secrets.token_hex(4)
    secret = f"cc_{prefix}_{secrets.token_urlsafe(32)}"
    now = datetime.now(UTC)
    doc = {
        "name": body.name.strip(),
        "prefix": prefix,
        "hash": token_hash(secret),
        "scopes": sorted(set(body.scopes)),
        "created_by": ctx.user_id,
        "created_at": now,
        "expires_at": now + timedelta(days=body.valid_days),
    }
    doc["_id"] = get_db().api_keys.insert_one(doc).inserted_id
    audit.record(
        "api_keys.created",
        actor_id=ctx.user_id,
        ip=ip,
        details={"name": doc["name"], "prefix": prefix, "scopes": doc["scopes"]},
    )
    return {**_view(doc), "key": secret}


def revoke(ctx: AuthContext, key_id: str, ip: str) -> dict[str, Any]:
    k = get_db().api_keys.find_one_and_update(
        {"_id": students.oid(key_id, "Key"), "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(UTC), "revoked_by": ctx.user_id}},
        return_document=True,
    )
    if not k:
        raise AppError(404, "Key not found or already revoked.")
    audit.record("api_keys.revoked", actor_id=ctx.user_id, ip=ip, details={"name": k["name"], "prefix": k["prefix"]})
    return _view(k)


def _parse(authorization: str | None, x_api_key: str | None) -> str:
    raw = x_api_key or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
    if not raw or not raw.startswith("cc_") or raw.count("_") < 2:
        raise AppError(401, "Send your API key in the Authorization header: Bearer cc_…", "unauthorized")
    return raw


def require_scope(scope: str):  # noqa: ANN201 - a FastAPI dependency factory
    def dependency(authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict[str, Any]:
        raw = _parse(authorization, x_api_key)
        prefix = raw.split("_")[1]
        db = get_db()
        k = db.api_keys.find_one({"prefix": prefix})
        now = datetime.now(UTC)
        if (
            not k
            or not hmac.compare_digest(k["hash"], token_hash(raw))
            or k.get("revoked_at")
            or k["expires_at"] <= now
        ):
            raise AppError(401, "This API key is not valid.", "unauthorized")
        if scope not in k["scopes"]:
            raise AppError(403, f"This key does not have the {scope} scope.", "forbidden")
        hit(
            f"apikey:{prefix}",
            limit=PER_HOUR,
            window_seconds=3600,
            message="Too many calls with this key. Try again later.",
        )
        update: dict[str, Any] = {"$inc": {"calls": 1}}
        if not k.get("last_used_at") or now - k["last_used_at"] > timedelta(minutes=5):
            update["$set"] = {"last_used_at": now}
        db.api_keys.update_one({"_id": k["_id"]}, update)
        return k

    return dependency
