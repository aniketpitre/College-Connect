from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.fees import approvals, scholarships, service
from app.modules.fees.schemas import (
    ChargeIn,
    ConcessionIn,
    Decision,
    FeeHeadIn,
    FeeHeadUpdate,
    GenerateDemands,
    ScholarshipAction,
    ScholarshipIn,
    StructureIn,
    StructureUpdate,
)
from app.modules.students import service as students

router = APIRouter(tags=["fees"])
READ = Depends(require(P.FEES_READ))
MANAGE = Depends(require(P.FEES_MANAGE))
COLLECT = Depends(require(P.FEES_COLLECT))
DECIDE = Depends(require(P.APPROVALS_DECIDE))


def year_or_current(academic_year_id: str | None) -> Any:
    if academic_year_id:
        return service.oid(academic_year_id, "Academic year")
    current = get_db().academic_years.find_one({"is_current": True})
    if not current:
        raise AppError(409, "Set the current academic year in College setup.", "no_current_year")
    return current["_id"]


# --- fee heads and structures ---------------------------------------------------------------


@router.get("/fees/heads")
def heads(ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.list_heads()


@router.post("/fees/heads", status_code=201)
def create_head(body: FeeHeadIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_head(ctx, body, client_ip(request))


@router.post("/fees/heads/starter")
def starter_heads(request: Request, ctx: AuthContext = MANAGE) -> dict[str, int]:
    return service.load_starter_heads(ctx, client_ip(request))


@router.patch("/fees/heads/{head_id}")
def update_head(head_id: str, body: FeeHeadUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_head(ctx, head_id, body, client_ip(request))


@router.get("/fees/structures")
def structures(
    academic_year_id: str | None = None, programme_id: str | None = None, ctx: AuthContext = READ
) -> list[dict]:
    return service.list_structures(academic_year_id, programme_id)


@router.post("/fees/structures", status_code=201)
def create_structure(body: StructureIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_structure(ctx, body, client_ip(request))


@router.put("/fees/structures/{structure_id}")
def update_structure(structure_id: str, body: StructureUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict:
    return service.update_structure(ctx, structure_id, body, client_ip(request))


@router.post("/fees/demands/generate")
def generate(body: GenerateDemands, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.generate_demands(ctx, body, client_ip(request))


# --- a student's account --------------------------------------------------------------------


@router.get("/fees/students/{student_id}")
def account(student_id: str, academic_year_id: str | None = None, ctx: AuthContext = READ) -> dict[str, Any]:
    student = students.get_student(service.oid(student_id, "Student"))
    result = service.account(student["_id"], year_or_current(academic_year_id))
    result["student"] = students.summary(student)
    return result


@router.post("/fees/students/{student_id}/charges")
def add_charge(student_id: str, body: ChargeIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_charge(ctx, student_id, body, client_ip(request))


@router.post("/fees/students/{student_id}/late-fees")
def late_fees(
    student_id: str, request: Request, academic_year_id: str = Query(...), ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return service.apply_late_fees(ctx, student_id, academic_year_id, client_ip(request))


# --- concessions, scholarships and approvals -----------------------------------------------


@router.post("/fees/concessions", status_code=201)
def request_concession(body: ConcessionIn, request: Request, ctx: AuthContext = COLLECT) -> dict[str, Any]:
    return approvals.request_concession(ctx, body, client_ip(request))


@router.get("/fees/scholarships")
def list_scholarships(
    student_id: str | None = None, academic_year_id: str | None = None, ctx: AuthContext = READ
) -> list[dict]:
    return scholarships.list_for(student_id, academic_year_id)


@router.post("/fees/scholarships", status_code=201)
def create_scholarship(body: ScholarshipIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return scholarships.create(ctx, body, client_ip(request))


@router.post("/fees/scholarships/{scholarship_id}/actions")
def scholarship_action(
    scholarship_id: str, body: ScholarshipAction, request: Request, ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return scholarships.act(ctx, scholarship_id, body, client_ip(request))


@router.get("/approvals")
def list_approvals(
    status: str | None = Query("pending", pattern="^(pending|approved|rejected)$"),
    kind: str | None = None,
    student_id: str | None = None,
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return approvals.list_requests(status, student_id, kind)


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: str, body: Decision, request: Request, ctx: AuthContext = DECIDE) -> dict[str, Any]:
    return approvals.decide(ctx, approval_id, body.approve, body.reason, client_ip(request))
