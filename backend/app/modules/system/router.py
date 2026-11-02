import time

from fastapi import APIRouter
from pymongo.errors import PyMongoError

from app.core.db import db_available, get_client
from app.rag.pipeline import pipeline_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "rag_pipeline": pipeline_status(), "analytics": db_available(), "db_ms": _db_ms()}


def _db_ms() -> float | None:
    """One round trip to the database, in milliseconds (shows if the app and database are far apart)."""
    if not db_available():
        return None
    try:
        started = time.perf_counter()
        get_client().admin.command("ping")
        return round((time.perf_counter() - started) * 1000, 1)
    except PyMongoError:
        return None
