from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.modules.messaging import service

router = APIRouter(tags=["messaging"])


class Channels(BaseModel):
    email: bool = True
    sms: bool = True
    whatsapp: bool = True


@router.get("/me/notifications")
def my_settings(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.my_settings(ctx)


@router.put("/me/notifications")
def set_settings(body: Channels, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.set_settings(ctx, body.model_dump())


@router.get("/messages/log")
def log(
    template: str | None = Query(None, max_length=40),
    status: str | None = Query(None, pattern="^(sent|failed)$"),
    student_id: str | None = None,
    ctx: AuthContext = Depends(require(P.MESSAGES_READ)),
) -> dict[str, Any]:
    return service.log(template=template, status=status, student_id=student_id)


@router.post("/messages/queue/run")
def run_queue(ctx: AuthContext = Depends(require(P.MESSAGES_READ))) -> dict[str, int]:
    """Sends queued messages now, for up to ~8 seconds; call again while `waiting` > 0."""
    return service.process_queue()
