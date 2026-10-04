"""
Shared test setup.

Environment is fixed *before* the app is imported so tests never reach a real Atlas
cluster or a paid AI API, whatever is in backend/.env:
  - MongoDB: TEST_MONGODB_URI (default: a local replica set on localhost:27017),
    database "collegeconnect_test", dropped before each database test.
  - AI keys blank: retrieval runs in keyword (BM25) mode and answers are document excerpts.
"""

import os

import pytest

TEST_MONGODB_URI = os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true")
TEST_DB = "collegeconnect_test"

os.environ["MONGODB_URI"] = TEST_MONGODB_URI
os.environ["MONGODB_DB"] = TEST_DB
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["VOYAGE_API_KEY"] = ""
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402
from pymongo.errors import PyMongoError  # noqa: E402


def _mongo_reachable() -> bool:
    try:
        MongoClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=1500).admin.command("ping")
        return True
    except PyMongoError:
        return False


MONGO_OK = _mongo_reachable()
requires_mongo = pytest.mark.skipif(
    not MONGO_OK, reason=f"MongoDB not reachable at {TEST_MONGODB_URI} (CI starts one; locally run a replica set)"
)


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db():
    """A clean test database for each test that asks for it, on the app's own client."""
    if not MONGO_OK:
        pytest.skip("MongoDB not reachable")
    from app.core import db as core_db

    mongo = core_db.get_client()
    mongo.drop_database(TEST_DB)
    core_db._indexes_ready = False
    yield mongo[TEST_DB]
    mongo.drop_database(TEST_DB)
    core_db._indexes_ready = False
