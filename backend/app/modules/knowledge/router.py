from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, require
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.helpdesk import analytics
from app.modules.knowledge import service

router = APIRouter(prefix="/kb", tags=["knowledge base"])
MANAGE = Depends(require(P.KB_MANAGE))


@router.get("/documents")
def documents(ctx: AuthContext = MANAGE) -> dict[str, Any]:
    """The help desk's documents (bundled, uploaded, typed and notices) and how search is running."""
    return service.list_documents()


@router.post("/documents", status_code=201)
async def add(
    request: Request,
    title: str = Form(..., max_length=200),
    category: str = Form(...),
    audience: str = Form("public"),
    text: str = Form("", max_length=service.MAX_TEXT),
    file: UploadFile | None = File(None),
    ctx: AuthContext = MANAGE,
) -> dict[str, Any]:
    """A PDF, .md or .txt file, or typed text. `audience`: public (the public help desk too) or
    everyone (signed-in students, parents and staff only)."""
    data = await file.read(MAX_BYTES + 1) if file is not None else None
    return service.add_document(
        ctx,
        title=title,
        category=category,
        audience=audience,
        text=text,
        filename=file.filename or "document" if file is not None else "",
        data=data,
        ip=client_ip(request),
    )


@router.delete("/documents/{doc_id}")
def remove(doc_id: str, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.remove_document(ctx, doc_id, client_ip(request))


@router.post("/reindex")
def reindex(request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    """Indexes notices that changed while indexing failed and adds missing embeddings (a batch per call)."""
    return service.reindex(ctx, client_ip(request))


class GapAnswerIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=500)
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., max_length=5000)
    category: str = "notices"
    audience: str = "public"


class GapIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=500)


@router.get("/gaps")
def gaps(days: int = Query(30, ge=1, le=90), ctx: AuthContext = MANAGE) -> list[dict[str, Any]]:
    """Questions the help desk couldn't answer, grouped, most asked first (what to publish next)."""
    return analytics.gaps(days)


@router.post("/gaps/answer", status_code=201)
def answer_gap(body: GapAnswerIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.answer_gap(
        ctx, body.key, body.question, body.answer, body.category, body.audience, client_ip(request)
    )


@router.post("/gaps/dismiss")
def dismiss_gap(body: GapIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.dismiss_gap(ctx, body.key, client_ip(request))
