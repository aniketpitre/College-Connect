"""
MongoDB access shared by every module.

- One client per serverless instance, reused across requests, with short timeouts so an
  outage fails fast instead of hanging requests.
- Modules declare their indexes with `register_indexes`; they are created once per
  process, the first time the database is used.
- `run_in_transaction` runs a callback in a multi-document transaction (requires a replica
  set, which Atlas always is) and retries transient errors.
"""

import logging
from collections.abc import Callable
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


def get_db() -> Database[dict[str, Any]]:
    global _indexes_ready
    database = get_client()[settings.mongodb_db]
    if not _indexes_ready:
        ensure_indexes(database)
        _indexes_ready = True
    return database


def run_in_transaction[T](callback: Callable[[ClientSession], T]) -> T:
    """Run `callback(session)` atomically. Pass `session=session` to every database call inside it."""
    with get_client().start_session() as session:
        return session.with_transaction(callback)
