from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.auth import AuthContext, signed_in
from app.core.requestinfo import base_url, client_ip
from app.modules.certificates import certificate_pdf, service
from app.modules.certificates.schemas import ActionIn, OfficeRequestIn, RequestIn, TypeUpdate
from app.modules.fees.receipts import verify_url
from app.modules.setup import service as setup

router = APIRouter(tags=["certificates"])
ME = Depends(signed_in)


def _pdf(cert: dict[str, Any], request: Request) -> Response:
    data = certificate_pdf.build(cert, setup.institution(), verify_url(base_url(request), cert["verify_code"]))
    name = cert["number"].replace("/", "-")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}.pdf"', "Cache-Control": "private, no-store"},
    )


@router.get("/certificates/types")
def types(ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.types()


@router.put("/certificates/types/{key}")
def update_type(key: str, body: TypeUpdate, request: Request, ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.update_type(ctx, key, body, client_ip(request))


@router.get("/certificates/requests")
def queue(status: str | None = None, ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.queue(ctx, status)


@router.post("/certificates/requests", status_code=201)
def request_for(body: OfficeRequestIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.request_for(ctx, body, client_ip(request))


@router.post("/certificates/requests/{request_id}/action")
def act(request_id: str, body: ActionIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.act(ctx, request_id, body.action, body.reason, client_ip(request))


@router.get("/certificates/requests/{request_id}/pdf")
def staff_pdf(request_id: str, request: Request, ctx: AuthContext = ME) -> Response:
    cert, _ = service.certificate_for_staff(ctx, request_id)
    return _pdf(cert, request)


@router.get("/certificates/no-dues")
def no_dues(prn: str = Query(..., min_length=1, max_length=40), ctx: AuthContext = ME) -> dict[str, Any]:
    return service.no_dues(ctx, prn)


@router.get("/me/certificates")
def mine(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.mine(ctx)


@router.post("/me/certificates", status_code=201)
def request_mine(body: RequestIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.request_mine(ctx, body, client_ip(request))


@router.get("/me/certificates/{request_id}/pdf")
def my_pdf(request_id: str, request: Request, ctx: AuthContext = ME) -> Response:
    cert, _ = service.certificate_for_student(ctx, request_id)
    return _pdf(cert, request)
