from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.parents import service
from app.modules.parents.schemas import Access, CodeRequest, CodeVerify, ParentLink
from app.modules.students.service import oid

router = APIRouter(tags=["parents"])


@router.post("/auth/otp/request")
def request_code(body: CodeRequest, request: Request) -> dict[str, Any]:
    """Parents: send a sign-in code for this mobile number (same answer whether or not it is registered)."""
    assert body.phone
    return service.request_code(request, body.phone)


@router.post("/auth/otp/verify")
def verify_code(body: CodeVerify, request: Request, response: Response) -> dict[str, Any]:
    assert body.phone
    return service.verify_code(request, response, body.phone, body.code)


@router.get("/parent/children")
def my_children(ctx: AuthContext = Depends(signed_in)) -> list[dict[str, Any]]:
    return service.children(ctx)


@router.get("/me/parent-access")
def my_sharing(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.my_sharing(ctx)


@router.put("/me/parent-access")
def set_sharing(body: Access, request: Request, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.set_sharing(ctx, body, client_ip(request))


@router.get("/students/{student_id}/parents")
def parents_of(student_id: str, ctx: AuthContext = Depends(require(P.STUDENTS_READ))) -> dict[str, Any]:
    return service.parents_of(oid(student_id))


@router.post("/students/{student_id}/parents", status_code=201)
def link(
    student_id: str, body: ParentLink, request: Request, ctx: AuthContext = Depends(require(P.STUDENTS_MANAGE))
) -> dict[str, Any]:
    return service.link(ctx, oid(student_id), body, client_ip(request))


@router.delete("/students/{student_id}/parents/{parent_id}")
def unlink(
    student_id: str, parent_id: str, request: Request, ctx: AuthContext = Depends(require(P.STUDENTS_MANAGE))
) -> dict[str, Any]:
    return service.unlink(ctx, oid(student_id), parent_id, client_ip(request))
