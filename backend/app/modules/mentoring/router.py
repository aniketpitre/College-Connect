from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.mentoring import service
from app.modules.mentoring.schemas import AssignIn, NoteIn, RiskRules

router = APIRouter(tags=["mentoring"])
ME = Depends(signed_in)  # the service checks who may see which students


@router.get("/risk")
def at_risk(
    level: str | None = Query(None, pattern="^(high|medium)$"),
    division_id: str | None = Query(None, max_length=40),
    ctx: AuthContext = ME,
) -> dict[str, Any]:
    return service.at_risk(ctx, level, division_id)


@router.post("/risk/recompute")
def recompute(ctx: AuthContext = Depends(require(P.RISK_MANAGE))) -> dict[str, int]:
    return service.compute()


@router.get("/risk/rules")
def get_rules(ctx: AuthContext = ME) -> dict[str, Any]:
    service.scope(ctx)
    return service.rules()


@router.put("/risk/rules")
def save_rules(body: RiskRules, ctx: AuthContext = Depends(require(P.RISK_MANAGE))) -> dict[str, Any]:
    return service.save_rules(ctx, body)


@router.get("/risk/students/{student_id}")
def detail(student_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.detail(ctx, student_id)


@router.post("/risk/students/{student_id}/notes", status_code=201)
def add_note(student_id: str, body: NoteIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.add_note(ctx, student_id, body)


@router.get("/mentoring/mentees")
def mentees(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.mentees(ctx)


@router.get("/mentoring/assignments")
def assignments(division_id: str = Query(..., max_length=40), ctx: AuthContext = ME) -> dict[str, Any]:
    return service.assignments(ctx, division_id)


@router.put("/mentoring/assignments")
def assign(body: AssignIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.assign(ctx, body, client_ip(request))
