"""Fixed-window rate limits stored in MongoDB (works across serverless instances)."""

from datetime import UTC, datetime, timedelta

from pymongo import IndexModel
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db, register_indexes
from app.core.errors import AppError

# Expired windows are removed automatically by MongoDB.
register_indexes("rate_limits", [IndexModel([("expires_at", 1)], expireAfterSeconds=0)])


def hit(
    key: str, limit: int, window_seconds: int, message: str = "Too many attempts. Please wait and try again."
) -> None:
    now = datetime.now(UTC)
    coll = get_db().rate_limits
    doc = coll.find_one_and_update(
        {"_id": key, "expires_at": {"$gt": now}},
        {"$inc": {"count": 1}},
        return_document=True,
    )
    if doc is None:
        try:
            coll.replace_one(
                {"_id": key}, {"count": 1, "expires_at": now + timedelta(seconds=window_seconds)}, upsert=True
            )
        except DuplicateKeyError:  # another request started the window at the same moment
            return hit(key, limit, window_seconds, message)
        return
    if doc["count"] > limit:
        raise AppError(429, message, "rate_limited")
