from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.grievance import service
from app.modules.grievance.schemas import ActionIn, CommentIn, FeedbackIn, GrievanceIn, SlaSettings

router = APIRouter(tags=["grievance"])
ME = Depends(signed_in)  # staff endpoints check the grievance permissions in the service


@router.get("/grievances")
def listing(
    status: str = Query("open", pattern="^(open|overdue|resolved|closed)$"),
    category: str | None = Query(None, max_length=20),
    ctx: AuthContext = ME,
) -> list[dict[str, Any]]:
    return service.listing(ctx, status, category)


@router.get("/grievances/stats")
def stats(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.stats(ctx)


@router.get("/grievances/settings")
def get_settings(ctx: AuthContext = Depends(require(P.GRIEVANCE_MANAGE))) -> dict[str, Any]:
    return service.settings()


@router.put("/grievances/settings")
def save_settings(body: SlaSettings, ctx: AuthContext = Depends(require(P.GRIEVANCE_MANAGE))) -> dict[str, Any]:
    return service.save_settings(ctx, body)


@router.get("/grievances/{grievance_id}")
def detail(grievance_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.detail(ctx, grievance_id)


@router.post("/grievances/{grievance_id}/action")
def act(grievance_id: str, body: ActionIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.act(ctx, grievance_id, body, client_ip(request))


@router.get("/me/grievances")
def mine(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_grievances(ctx)


@router.post("/me/grievances", status_code=201)
def raise_grievance(body: GrievanceIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.raise_grievance(ctx, body)


@router.get("/me/grievances/{grievance_id}")
def my_one(grievance_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_grievance(ctx, grievance_id)


@router.post("/me/grievances/{grievance_id}/comment")
def comment(grievance_id: str, body: CommentIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.comment(ctx, grievance_id, body.text)


@router.post("/me/grievances/{grievance_id}/feedback")
def feedback(grievance_id: str, body: FeedbackIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.feedback(ctx, grievance_id, body)
