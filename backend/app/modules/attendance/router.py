from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from app.core import clock
from app.core.auth import AuthContext, require, signed_in
from app.core.config import settings
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.attendance import service, stats
from app.modules.attendance.schemas import DecideIn, EditRequestIn, ExemptionIn, MarkIn

router = APIRouter(tags=["attendance"])
TAKE = Depends(require(P.ATTENDANCE_TAKE))
EXEMPT = Depends(require(P.ATTENDANCE_EXEMPT))


def _staff(ctx: AuthContext = Depends(signed_in)) -> AuthContext:
    if not ctx.permissions & {P.ATTENDANCE_TAKE, P.ATTENDANCE_READ, P.ATTENDANCE_READ_DEPT, P.ATTENDANCE_APPROVE}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return ctx


STAFF = Depends(_staff)


class ReasonIn(BaseModel):
    reason: str | None = Field(None, max_length=300)


@router.get("/attendance/today")
def today(day: date | None = None, ctx: AuthContext = TAKE) -> dict[str, Any]:
    return service.today(ctx, day or clock.today())


@router.get("/attendance/sheet")
def sheet(slot_id: str, day: date, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.sheet(ctx, slot_id, day)


@router.put("/attendance/sheet")
def save(body: MarkIn, request: Request, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.save(ctx, body, client_ip(request))


@router.post("/attendance/edit-requests", status_code=201)
def request_edit(body: EditRequestIn, request: Request, ctx: AuthContext = TAKE) -> dict[str, Any]:
    return service.request_edit(ctx, body, client_ip(request))


@router.get("/attendance/edit-requests")
def list_requests(status: str | None = None, ctx: AuthContext = STAFF) -> list[dict[str, Any]]:
    return service.list_requests(ctx, status)


@router.post("/attendance/edit-requests/{request_id}/decide")
def decide(
    request_id: str, body: DecideIn, request: Request, ctx: AuthContext = Depends(require(P.ATTENDANCE_APPROVE))
) -> dict[str, Any]:
    return service.decide(ctx, request_id, body.approve, body.reason, client_ip(request))


@router.post("/attendance/exemptions", status_code=201)
def add_exemption(body: ExemptionIn, request: Request, ctx: AuthContext = EXEMPT) -> dict[str, Any]:
    return service.add_exemption(ctx, body, client_ip(request))


@router.get("/attendance/exemptions")
def list_exemptions(student_id: str | None = None, ctx: AuthContext = EXEMPT) -> list[dict[str, Any]]:
    return service.list_exemptions(student_id)


@router.post("/attendance/exemptions/{exemption_id}/cancel", status_code=204)
def cancel_exemption(exemption_id: str, body: ReasonIn, request: Request, ctx: AuthContext = EXEMPT) -> None:
    service.cancel_exemption(ctx, exemption_id, body.reason, client_ip(request))


@router.get("/attendance/classes")
def classes(ctx: AuthContext = STAFF) -> list[dict[str, Any]]:
    """Classes whose attendance this person may see."""
    return stats.readable_divisions(ctx)


@router.get("/attendance/report")
def report(
    division_id: str, date_from: date | None = None, date_to: date | None = None, ctx: AuthContext = STAFF
) -> dict[str, Any]:
    return stats.division_report(ctx, division_id, date_from, date_to)


@router.get("/me/attendance")
def my_attendance(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return stats.my_attendance(ctx)


@router.get("/cron/attendance-alerts", include_in_schema=False)
def attendance_alerts(authorization: str | None = Header(None)) -> dict[str, int]:
    if not settings.cron_secret or authorization != f"Bearer {settings.cron_secret}":
        raise AppError(401, "Not allowed.", "unauthorized")
    return stats.send_alerts()
