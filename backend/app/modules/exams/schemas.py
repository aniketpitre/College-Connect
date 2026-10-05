from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Time = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ClassIn(BaseModel):
    programme_id: str
    year_of_study: int = Field(..., ge=1, le=6)


class PaperIn(BaseModel):
    subject_id: str
    date: date
    start: str = Time
    end: str = Time

    @model_validator(mode="after")
    def _times(self) -> "PaperIn":
        if self.end <= self.start:
            raise ValueError("end: The paper must end after it starts.")
        return self


class SessionIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    kind: Literal["university", "internal"] = "university"
    term: int = Field(..., ge=1, le=3)
    classes: list[ClassIn] = Field(..., min_length=1, max_length=40)
    form_deadline: date
    fee_head_code: str | None = Field(
        "EXAM", max_length=20, description="Fee head that must be paid; empty = no fee check"
    )
    seat_prefix: str = Field("", max_length=8, pattern=r"^[A-Z0-9]*$")


class SessionUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=120)
    form_deadline: date | None = None
    papers: list[PaperIn] | None = Field(None, max_length=200)
    hall_tickets_released: bool | None = None


class VerifyIn(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)
