"""
The assistant panel in every portal (plan 5.3): the help desk for signed-in people, answering
from the documents and notices they may see (`access.chunk_filter`). Questions are logged like
the public help desk's (question, language, which document answered), never with who asked.
"""

import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core import ratelimit
from app.core.auth import AuthContext, signed_in
from app.modules.assistant.access import chunk_filter
from app.modules.helpdesk.analytics import log_query
from app.modules.helpdesk.schemas import QueryRequest
from app.rag.pipeline import answer_question

router = APIRouter(prefix="/assistant", tags=["assistant"])
ME = Depends(signed_in)


@router.post("/ask")
def ask(body: QueryRequest, background: BackgroundTasks, ctx: AuthContext = ME) -> dict[str, Any]:
    ratelimit.hit(f"assistant:{ctx.user_id}", 60, 3600, "You've asked a lot this hour. Please try again later.")
    started = time.perf_counter()
    result = answer_question(body.question, body.language, body.category, chunk_filter(ctx))
    latency_ms = round((time.perf_counter() - started) * 1000)
    background.add_task(log_query, body.question, body.language, body.category, result, latency_ms, "portal")
    return {**result, "language": body.language}
