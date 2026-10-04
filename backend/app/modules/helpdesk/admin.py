"""
Help-desk analytics for staff.

Protected by the ADMIN_TOKEN bearer token until Phase 1 (PR 1.2) replaces it with real
staff accounts and roles.
"""

import os
import secrets

from fastapi import APIRouter, Depends, Header, Query
from pymongo.errors import PyMongoError

from app.core.db import db_available
from app.core.errors import AppError
from app.modules.helpdesk.analytics import admin_stats
from app.rag.pipeline import pipeline_status

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        raise AppError(503, "Admin portal is disabled: set ADMIN_TOKEN on the server.")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied.encode(), token.encode()):
        raise AppError(401, "Invalid admin token.")


@router.get("/stats", dependencies=[Depends(require_admin)])
def get_stats(days: int = Query(7, ge=1, le=90)) -> dict:
    base = {"pipeline": pipeline_status(), "analytics_enabled": db_available()}
    if not db_available():
        return base
    try:
        return {**base, **admin_stats(days)}
    except PyMongoError as e:
        raise AppError(503, f"Database unavailable: {type(e).__name__}") from e
