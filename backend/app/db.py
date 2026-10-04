"""
MongoDB Atlas connection, used for query logs (admin analytics).

The database is optional: without MONGODB_URI the help desk still answers questions,
it just doesn't record them and the admin stats endpoint reports that analytics are off.
"""
import logging
import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

import app.rag.config  # noqa: F401  (loads backend/.env for local dev)

log = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "collegeconnect")


def db_available() -> bool:
    return bool(MONGODB_URI)


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    # One client per serverless instance, reused across requests. Short timeouts so a
    # database outage degrades analytics instead of hanging student requests.
    return MongoClient(
        MONGODB_URI,
        appname="collegeconnect",
        tz_aware=True,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
        maxPoolSize=5,
    )


def get_db() -> Database:
    return _client()[MONGODB_DB]
