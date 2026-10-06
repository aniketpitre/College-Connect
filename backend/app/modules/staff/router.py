from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.staff import service
from app.modules.staff.schemas import AdjustIn, DecideIn, LeaveIn, LeaveSettings, StaffProfileIn

router = APIRouter(tags=["staff"])
ME = Depends(signed_in)  # staff lists check STAFF_READ / STAFF_READ_DEPT in the service
MANAGE = Depends(require(P.STAFF_MANAGE))
APPLY = Depends(require(P.LEAVE_APPLY))


@router.get("/staff")
def staff_list(ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.staff_list(ctx)


@router.get("/staff/summary")
def summary(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.summary(ctx)


@router.get("/staff/workload")
def workload(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.workload(ctx)


@router.get("/staff/me")
def my_profile(ctx: AuthContext = APPLY) -> dict[str, Any]:
    return service.my_profile(ctx)


@router.get("/staff/{user_id}")
def profile(user_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.profile(ctx, user_id)


@router.put("/staff/{user_id}")
def save_profile(user_id: str, body: StaffProfileIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.save_profile(ctx, user_id, body, client_ip(request))


@router.get("/staff/{user_id}/leave")
def staff_leave(user_id: str, ctx: AuthContext = ME) -> list[dict[str, Any]]:
    u = service.profile(ctx, user_id)
    return service.balances(service.oid(u["user_id"], "Staff member"))


@router.get("/leave/settings")
def leave_settings(ctx: AuthContext = APPLY) -> list[dict[str, Any]]:
    return service.leave_types()


@router.put("/leave/settings")
def save_leave_settings(body: LeaveSettings, ctx: AuthContext = MANAGE) -> list[dict[str, Any]]:
    return service.save_leave_settings(ctx, body)


@router.post("/leave/adjustments")
def adjust(body: AdjustIn, request: Request, ctx: AuthContext = MANAGE) -> list[dict[str, Any]]:
    return service.adjust(ctx, body, client_ip(request))


@router.get("/leave/requests")
def to_decide(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    ctx: AuthContext = Depends(require(P.LEAVE_APPROVE)),
) -> list[dict[str, Any]]:
    return service.requests_to_decide(ctx, status)


@router.post("/leave/requests/{request_id}/decide")
def decide(
    request_id: str, body: DecideIn, request: Request, ctx: AuthContext = Depends(require(P.LEAVE_APPROVE))
) -> dict[str, Any]:
    return service.decide(ctx, request_id, body, client_ip(request))


@router.get("/me/leave")
def my_leave(ctx: AuthContext = APPLY) -> dict[str, Any]:
    return service.my_leave(ctx)


@router.post("/me/leave", status_code=201)
def apply(body: LeaveIn, request: Request, ctx: AuthContext = APPLY) -> dict[str, Any]:
    return service.apply(ctx, body, client_ip(request))


@router.post("/me/leave/{request_id}/cancel")
def cancel(request_id: str, request: Request, ctx: AuthContext = APPLY) -> dict[str, Any]:
    return service.cancel(ctx, request_id, client_ip(request))
