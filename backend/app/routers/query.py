from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse
from app.rag.pipeline import answer_question

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def ask_question(request: QueryRequest) -> QueryResponse:
    result = answer_question(request.question, request.language, request.category)
    return QueryResponse(
        answer=result["answer"],
        language=request.language,
        category=result["category"],
        sources=result["sources"],
        confidence=result["confidence"],
        grounded=result["grounded"],
    )
