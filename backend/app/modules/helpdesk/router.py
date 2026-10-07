"""The help desk's question endpoint (signed-in people only) and the list of offices it answers about.

Since the home page replaced the public help desk, answers need a sign-in: each person is answered
from the documents and notices they may see (`assistant.access.chunk_filter`; applicants see the
documents marked public). The portal's Ask panel uses `/assistant/ask`, which adds the person's own
record; `/query` stays for older links and the legacy `/api/query` alias."""

import time

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.auth import AuthContext, signed_in
from app.modules.assistant.access import chunk_filter
from app.modules.helpdesk.analytics import log_query
from app.modules.helpdesk.schemas import CategoryInfo, QueryRequest, QueryResponse
from app.rag.pipeline import answer_question

router = APIRouter(tags=["help desk"])

CATEGORIES: list[CategoryInfo] = [
    CategoryInfo(id="admissions", label_en="Admissions", label_hi="प्रवेश", label_mr="प्रवेश"),
    CategoryInfo(id="fees", label_en="Fees & Accounts", label_hi="शुल्क एवं लेखा", label_mr="शुल्क आणि लेखा"),
    CategoryInfo(id="examinations", label_en="Examinations", label_hi="परीक्षा", label_mr="परीक्षा"),
    CategoryInfo(id="placements", label_en="Placements", label_hi="प्लेसमेंट", label_mr="नोकरी नियुक्ती"),
    CategoryInfo(id="hostel", label_en="Hostel & Campus", label_hi="छात्रावास एवं परिसर", label_mr="वसतिगृह आणि आवार"),
    CategoryInfo(id="notices", label_en="Notices & Announcements", label_hi="सूचनाएं", label_mr="सूचना"),
]


@router.get("/categories", response_model=list[CategoryInfo])
def get_categories() -> list[CategoryInfo]:
    return CATEGORIES


@router.post("/query", response_model=QueryResponse)
def ask_question(
    request: QueryRequest, background: BackgroundTasks, ctx: AuthContext = Depends(signed_in)
) -> QueryResponse:
    started = time.perf_counter()
    result = answer_question(request.question, request.language, request.category, chunk_filter(ctx))
    latency_ms = round((time.perf_counter() - started) * 1000)
    # Logged after the response is sent, so the database never slows down an answer.
    background.add_task(log_query, request.question, request.language, request.category, result, latency_ms, "portal")
    return QueryResponse(
        answer=result["answer"],
        language=request.language,
        category=result["category"],
        sources=result["sources"],
        confidence=result["confidence"],
        grounded=result["grounded"],
    )
