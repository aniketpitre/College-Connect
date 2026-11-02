"""
MongoDB access shared by every module.

- One client per serverless instance, reused across requests, with short timeouts so an
  outage fails fast instead of hanging requests.
- Modules declare their indexes with `register_indexes`. The first time a process uses the
  database it reads one small marker (a fingerprint of every declared index); only when that has
  changed are the indexes (re)created. A cold start therefore costs one round trip, not one per
  collection (60+, which over the network to Atlas took several seconds).
- `run_in_transaction` runs a callback in a multi-document transaction (requires a replica
  set, which Atlas always is) and retries transient errors.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from pymongo import IndexModel, MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.core.config import settings

log = logging.getLogger(__name__)

_index_registry: dict[str, list[IndexModel]] = {}
_indexes_ready = False


def db_available() -> bool:
    return bool(settings.mongodb_uri)


@lru_cache(maxsize=1)
def get_client() -> MongoClient[dict[str, Any]]:
    return MongoClient(
        settings.mongodb_uri,
        appname="collegeconnect",
        tz_aware=True,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
        maxPoolSize=5,
    )


def register_indexes(collection: str, indexes: list[IndexModel]) -> None:
    _index_registry.setdefault(collection, []).extend(indexes)


def ensure_indexes(database: Database[dict[str, Any]]) -> None:
    for collection, indexes in _index_registry.items():
        database[collection].create_indexes(indexes)


def index_fingerprint() -> str:
    """Changes whenever a module adds, removes or changes an index."""
    spec = sorted(
        (c, sorted(json.dumps(ix.document, sort_keys=True, default=str) for ix in ixs))
        for c, ixs in _index_registry.items()
    )
    return hashlib.sha256(json.dumps(spec).encode()).hexdigest()[:20]


def get_db() -> Database[dict[str, Any]]:
    global _indexes_ready
    database = get_client()[settings.mongodb_db]
    if not _indexes_ready:
        fingerprint = index_fingerprint()
        marker = database.app_meta.find_one({"_id": "indexes"}, {"fingerprint": 1})
        if not marker or marker.get("fingerprint") != fingerprint:
            ensure_indexes(database)
            database.app_meta.update_one(
                {"_id": "indexes"}, {"$set": {"fingerprint": fingerprint, "at": datetime.now(UTC)}}, upsert=True
            )
        _indexes_ready = True
    return database


def run_in_transaction[T](callback: Callable[[ClientSession], T]) -> T:
    """Run `callback(session)` atomically. Pass `session=session` to every database call inside it."""
    with get_client().start_session() as session:
        return session.with_transaction(callback)
