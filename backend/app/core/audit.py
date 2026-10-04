"""
Append-only audit log of security events and changes to money, marks, records and roles.

Entries are never updated or deleted by the application.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession

from app.core.db import get_db, register_indexes

register_indexes(
    "audit_log",
    [
        IndexModel([("at", DESCENDING)]),
        IndexModel([("actor_id", ASCENDING), ("at", DESCENDING)]),
        IndexModel([("target_type", ASCENDING), ("target_id", ASCENDING), ("at", DESCENDING)]),
        IndexModel([("action", ASCENDING), ("at", DESCENDING)]),
    ],
)


def record(
    action: str,
    *,
    actor_id: ObjectId | None = None,
    target_type: str | None = None,
    target_id: ObjectId | str | None = None,
    ip: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    session: ClientSession | None = None,
) -> None:
    entry: dict[str, Any] = {"at": datetime.now(UTC), "action": action}
    for key, value in (
        ("actor_id", actor_id),
        ("target_type", target_type),
        ("target_id", target_id),
        ("ip", ip),
        ("reason", reason),
        ("details", details),
    ):
        if value is not None:
            entry[key] = value
    get_db().audit_log.insert_one(entry, session=session)
