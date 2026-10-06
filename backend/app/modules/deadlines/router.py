import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.deadlines import service

router = APIRouter(tags=["deadlines"])
PUBLISH = Depends(require(P.NOTICES_PUBLISH))
ME = Depends(signed_in)


class DeadlineIn(BaseModel):
    date: dt.date
    what: str = Field(..., max_length=200)
    what_hi: str | None = Field(None, max_length=200)
    what_mr: str | None = Field(None, max_length=200)


class DecisionIn(BaseModel):
    status: Literal["confirmed", "dismissed"]
    date: dt.date | None = None
    what: str | None = Field(None, max_length=200)
    what_hi: str | None = Field(None, max_length=200)
    what_mr: str | None = Field(None, max_length=200)


@router.get("/notices/{notice_id}/deadlines")
def notice_deadlines(notice_id: str, ctx: AuthContext = PUBLISH) -> list[dict[str, Any]]:
    """Dates found in the notice (proposed) and those staff confirmed or dismissed."""
    return service.for_notice(notice_id)


@router.post("/notices/{notice_id}/deadlines/find")
def find_again(notice_id: str, ctx: AuthContext = PUBLISH) -> list[dict[str, Any]]:
    service.propose(service.oid(notice_id, "Notice"))
    return service.for_notice(notice_id)


@router.post("/notices/{notice_id}/deadlines", status_code=201)
def add(notice_id: str, body: DeadlineIn, request: Request, ctx: AuthContext = PUBLISH) -> dict[str, Any]:
    return service.add(ctx, notice_id, body.date, body.what, body.what_hi, body.what_mr, client_ip(request))


@router.patch("/deadlines/{deadline_id}")
def decide(deadline_id: str, body: DecisionIn, request: Request, ctx: AuthContext = PUBLISH) -> dict[str, Any]:
    """Confirm (optionally correcting the date or wording) or dismiss a deadline."""
    return service.decide(
        ctx,
        deadline_id,
        status=body.status,
        when=body.date,
        en=body.what,
        hi=body.what_hi,
        mr=body.what_mr,
        ip=client_ip(request),
    )


@router.get("/me/deadlines")
def mine(ctx: AuthContext = ME) -> list[dict[str, Any]]:
    """Students and parents: confirmed deadlines of their notices in the next two weeks."""
    return service.upcoming(ctx)
