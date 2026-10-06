from typing import Any

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, Response, UploadFile

from app.core import files
from app.core.auth import AuthContext, require, signed_in
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.core.requestinfo import base_url, client_ip
from app.modules.notices import service
from app.modules.notices.schemas import NoticeIn, NoticeUpdate, TranslateIn

router = APIRouter(tags=["notices"])
PUBLISH = Depends(require(P.NOTICES_PUBLISH))
ME = Depends(signed_in)


@router.get("/notices")
def list_notices(
    q: str | None = Query(None, max_length=100), manage: bool = False, ctx: AuthContext = ME
) -> list[dict[str, Any]]:
    """Notices this person can see (students: theirs; staff: everyone/staff; manage=true: all, for publishers)."""
    return service.list_notices(ctx, manage=manage, q=q)


def _translate_later(background: BackgroundTasks, notice: dict[str, Any]) -> None:
    """Missing Hindi/Marathi versions are filled in after the response, so publishing stays quick."""
    if notice["state"] in ("published", "scheduled") and not (notice["hi"] and notice["mr"]):
        background.add_task(service.auto_translate, ObjectId(notice["id"]))


@router.post("/notices", status_code=201)
def create(body: NoticeIn, request: Request, background: BackgroundTasks, ctx: AuthContext = PUBLISH) -> dict[str, Any]:
    notice = service.create(ctx, body, client_ip(request))
    _translate_later(background, notice)
    return notice


@router.post("/notices/translate")
def translate(body: TranslateIn, ctx: AuthContext = PUBLISH) -> dict[str, Any]:
    """Hindi and Marathi drafts for the form, for staff to check and edit before publishing."""
    return service.translate_for(ctx, body.title, body.body)


@router.get("/notices/{notice_id}")
def get_notice(notice_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.view(service.get_visible(ctx, notice_id))


@router.patch("/notices/{notice_id}")
def update(
    notice_id: str, body: NoticeUpdate, request: Request, background: BackgroundTasks, ctx: AuthContext = PUBLISH
) -> dict[str, Any]:
    notice = service.update(ctx, notice_id, body, client_ip(request))
    _translate_later(background, notice)
    return notice


@router.post("/notices/{notice_id}/attachment")
async def attach(notice_id: str, request: Request, file: UploadFile = File(...), ctx: AuthContext = PUBLISH) -> dict:
    data = await file.read(MAX_BYTES + 1)
    return service.attach(ctx, notice_id, file.filename or "notice.pdf", data, client_ip(request))


@router.get("/notices/{notice_id}/attachment")
def attachment(notice_id: str, ctx: AuthContext = ME) -> Response:
    n = service.get_visible(ctx, notice_id)
    if not n.get("attachment_file_id"):
        return Response(status_code=404)
    doc = files.load(str(n["attachment_file_id"]))
    return Response(
        content=bytes(doc["data"]),
        media_type=doc["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{doc["filename"]}"',
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.post("/notices/{notice_id}/email")
def email(notice_id: str, request: Request, ctx: AuthContext = PUBLISH) -> dict[str, Any]:
    return service.email_chunk(ctx, notice_id, base_url(request), client_ip(request))
