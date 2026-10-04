import time

from fastapi import APIRouter, BackgroundTasks

from app.analytics import log_query
from app.models import QueryRequest, QueryResponse
from app.rag.pipeline import answer_question

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def ask_question(request: QueryRequest, background: BackgroundTasks) -> QueryResponse:
    started = time.perf_counter()
    result = answer_question(request.question, request.language, request.category)
    latency_ms = round((time.perf_counter() - started) * 1000)
    # Logged after the response is sent, so the database never slows down an answer.
    background.add_task(log_query, request.question, request.language, request.category, result, latency_ms)
    return QueryResponse(
        answer=result["answer"],
        language=request.language,
        category=result["category"],
        sources=result["sources"],
        confidence=result["confidence"],
        grounded=result["grounded"],
    )
