"""Help-desk analytics for staff with the analytics.view permission."""

from fastapi import APIRouter, Depends, Query
from pymongo.errors import PyMongoError

from app.core.auth import AuthContext, require
from app.core.db import db_available
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.helpdesk.analytics import admin_stats
from app.rag.pipeline import pipeline_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def get_stats(days: int = Query(7, ge=1, le=90), ctx: AuthContext = Depends(require(P.ANALYTICS_VIEW))) -> dict:
    base = {"pipeline": pipeline_status(), "analytics_enabled": db_available()}
    if not db_available():
        return base
    try:
        return {**base, **admin_stats(days)}
    except PyMongoError as e:
        raise AppError(503, f"Database unavailable: {type(e).__name__}") from e
