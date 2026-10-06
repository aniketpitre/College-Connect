from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.auth import AuthContext, require
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.core.requestinfo import client_ip
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
