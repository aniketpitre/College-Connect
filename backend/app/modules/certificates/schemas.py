from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

CertType = Literal["bonafide", "character", "fee_paid", "tc", "migration", "noc"]


class RequestIn(BaseModel):
    type: CertType
    purpose: str = Field(..., min_length=3, max_length=200, description="e.g. Bank loan, passport, scholarship")
    reason_for_leaving: str | None = Field(None, max_length=200, description="TC / migration")
    organisation: str | None = Field(None, max_length=200, description="NOC: where the internship is")
    from_date: date | None = None
    to_date: date | None = None


class OfficeRequestIn(RequestIn):
    student_id: str


class ActionIn(BaseModel):
    action: Literal["verify", "sign", "issue", "reject"]
    reason: str | None = Field(None, max_length=300)


class TypeUpdate(BaseModel):
    promised_days: int = Field(..., ge=1, le=60)
    enabled: bool = True
