import json
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, require, signed_in
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.exports import full, service

router = APIRouter(tags=["exports"])


class ExportIn(BaseModel):
    dataset: str
    reason: str = Field(max_length=500)


class DecideIn(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=500)


def _requester_or_approver(ctx: AuthContext = Depends(signed_in)) -> AuthContext:
    if P.EXPORT_REQUEST not in ctx.permissions and P.APPROVALS_DECIDE not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return ctx


@router.get("/export/requests")
def list_requests(ctx: AuthContext = Depends(_requester_or_approver)) -> dict[str, Any]:
    return {"datasets": service.DATASETS, "requests": service.list_requests(ctx)}


@router.post("/export/requests", status_code=201)
def request_export(
    body: ExportIn, request: Request, ctx: AuthContext = Depends(require(P.EXPORT_REQUEST))
) -> dict[str, Any]:
    return service.request_export(ctx, body.dataset, body.reason, client_ip(request))


@router.post("/export/requests/{request_id}/decide")
def decide(
    request_id: str, body: DecideIn, request: Request, ctx: AuthContext = Depends(require(P.APPROVALS_DECIDE))
) -> dict[str, Any]:
    return service.decide(ctx, request_id, body.approve, body.reason, client_ip(request))


@router.get("/export/requests/{request_id}/download")
def download(request_id: str, request: Request, ctx: AuthContext = Depends(require(P.EXPORT_REQUEST))) -> Response:
    filename, data = service.download(ctx, request_id, client_ip(request))
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.get("/export/requests/{request_id}/full")
def full_manifest(
    request_id: str, request: Request, ctx: AuthContext = Depends(require(P.EXPORT_REQUEST))
) -> dict[str, Any]:
    r = service.approved_request(ctx, request_id)
    if r["dataset"] != "full":
        raise AppError(409, "This is not a full export.", "conflict")
    return full.manifest(ctx, r, client_ip(request))


@router.get("/export/requests/{request_id}/full/{collection}")
def full_page(
    request_id: str, collection: str, after: str | None = None, ctx: AuthContext = Depends(require(P.EXPORT_REQUEST))
) -> Response:
    r = service.approved_request(ctx, request_id)
    if r["dataset"] != "full":
        raise AppError(409, "This is not a full export.", "conflict")
    body, next_after = full.page(collection, after)
    headers = {"Cache-Control": "private, no-store"}
    if next_after:
        headers["X-Next-After"] = next_after
    return Response(content=body, media_type="application/x-ndjson", headers=headers)


@router.get("/me/data-export")
def my_data(request: Request, ctx: AuthContext = Depends(signed_in)) -> Response:
    data = service.my_data(ctx, client_ip(request))
    prn = data["student_record"]["prn"]
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="my-data-{prn}.json"',
            "Cache-Control": "private, no-store",
        },
    )
