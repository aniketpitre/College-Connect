import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pymongo.errors import PyMongoError

from app.analytics import admin_stats
from app.db import db_available
from app.rag.pipeline import pipeline_status

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        raise HTTPException(503, "Admin portal is disabled: set ADMIN_TOKEN on the server.")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(401, "Invalid admin token.")


@router.get("/stats", dependencies=[Depends(require_admin)])
def get_stats(days: int = Query(7, ge=1, le=90)) -> dict:
    status = pipeline_status()
    base = {"pipeline": status, "analytics_enabled": db_available()}
    if not db_available():
        return base
    try:
        return {**base, **admin_stats(days)}
    except PyMongoError as e:
        raise HTTPException(503, f"Database unavailable: {type(e).__name__}") from e
