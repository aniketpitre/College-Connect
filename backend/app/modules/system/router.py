from fastapi import APIRouter

from app.core.db import db_available
from app.rag.pipeline import pipeline_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "rag_pipeline": pipeline_status(), "analytics": db_available()}
