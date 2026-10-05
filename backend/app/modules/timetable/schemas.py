from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Time = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="24-hour HH:MM")


class TimetableIn(BaseModel):
    academic_year_id: str
    division_id: str
    term: int = Field(..., ge=1, le=3, description="1 = odd semester, 2 = even semester")
    valid_from: date
    valid_to: date

    @model_validator(mode="after")
    def _dates(self) -> "TimetableIn":
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to: The end date must be on or after the start date.")
        return self


class TimetableUpdate(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None


class SlotIn(BaseModel):
    day: int = Field(..., ge=1, le=6, description="1 = Monday … 6 = Saturday")
    start: str = Time
    end: str = Time
    subject_id: str
    faculty_ids: list[str] = Field(..., min_length=1, max_length=4)
    room: str = Field("", max_length=30)
    batch: str | None = Field(None, max_length=10, description="Practical batch, e.g. B1; empty = whole division")

    @field_validator("room")
    @classmethod
    def _room(cls, v: str) -> str:
        return " ".join(v.split()).upper()

    @field_validator("batch")
    @classmethod
    def _batch(cls, v: str | None) -> str | None:
        v = (v or "").strip().upper()
        return v or None

    @model_validator(mode="after")
    def _times(self) -> "SlotIn":
        if self.end <= self.start:
            raise ValueError("end: The lecture must end after it starts.")
        return self


class ChangeIn(BaseModel):
    date: date
    kind: Literal["cancelled", "substitute"]
    faculty_ids: list[str] = Field(default_factory=list, max_length=4)
    room: str = Field("", max_length=30)
    reason: str = Field(..., min_length=3, max_length=300)

    @model_validator(mode="after")
    def _who(self) -> "ChangeIn":
        if self.kind == "substitute" and not self.faculty_ids:
            raise ValueError("faculty_ids: Choose who takes the lecture.")
        return self
