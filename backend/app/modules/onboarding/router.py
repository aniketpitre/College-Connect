from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.auth import AuthContext, signed_in, signed_in_allow_password_change
from app.core.errors import AppError
from app.core.requestinfo import client_ip, user_agent
from app.modules.onboarding import service
from app.modules.students.schemas import clean_phone

router = APIRouter(prefix="/me", tags=["onboarding"])
Language = Literal["en", "hi", "mr"]


class OnboardingIn(BaseModel):
    phone: str
    email: EmailStr | None = None
    accept_privacy: bool
    privacy_version: str = Field(..., max_length=20)
    language: Language

    _phone = field_validator("phone")(clean_phone)

    @field_validator("accept_privacy")
    @classmethod
    def _accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please read and accept the privacy notice to continue.")
        return v


class PreferencesIn(BaseModel):
    language: Language


@router.get("/onboarding")
def onboarding_status(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.status(ctx)


@router.post("/onboarding")
def complete_onboarding(body: OnboardingIn, request: Request, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    if not body.phone:
        raise AppError(422, "Enter your mobile number.", field="phone")
    return service.complete(
        ctx,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        privacy_version=body.privacy_version,
        language=body.language,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )


@router.patch("/preferences", status_code=204)
def preferences(body: PreferencesIn, ctx: AuthContext = Depends(signed_in_allow_password_change)) -> None:
    service.set_language(ctx, body.language)
