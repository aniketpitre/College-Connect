from typing import Any

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, require, signed_in
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.fees.schemas import PositivePaise
from app.modules.payments import service

router = APIRouter(tags=["payments"])
MAX_CSV = 2 * 1024 * 1024


class StartIn(BaseModel):
    academic_year_id: str | None = None
    amount: int = PositivePaise


class ConfirmIn(BaseModel):
    razorpay_payment_id: str = Field(..., min_length=5, max_length=60)
    razorpay_signature: str = Field(..., min_length=20, max_length=200)


@router.post("/me/payments", status_code=201)
def start(body: StartIn, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.start(ctx, body.academic_year_id, body.amount)


@router.post("/me/payments/{payment_id}/confirm")
def confirm(
    payment_id: str, body: ConfirmIn, request: Request, ctx: AuthContext = Depends(signed_in)
) -> dict[str, Any]:
    return service.confirm(ctx, payment_id, body.razorpay_payment_id, body.razorpay_signature, client_ip(request))


@router.post("/payments/razorpay/webhook", include_in_schema=False)
async def webhook(request: Request, x_razorpay_signature: str | None = Header(None)) -> dict[str, Any]:
    body = await request.body()
    return service.webhook(body, x_razorpay_signature)


@router.get("/fees/online-payments")
def day_list(day: str | None = None, ctx: AuthContext = Depends(require(P.FEES_READ))) -> dict[str, Any]:
    return service.day_list(day)


@router.post("/fees/online-payments/{payment_id}/check")
def check(payment_id: str, request: Request, ctx: AuthContext = Depends(require(P.FEES_COLLECT))) -> dict[str, Any]:
    return service.check(ctx, payment_id, client_ip(request))


@router.post("/fees/online-payments/reconcile")
async def reconcile(file: UploadFile = File(...), ctx: AuthContext = Depends(require(P.FEES_READ))) -> dict[str, Any]:
    data = await file.read(MAX_CSV + 1)
    if len(data) > MAX_CSV:
        raise AppError(413, "The file is larger than 2 MB.", "too_large", "file")
    return service.reconcile(data)
