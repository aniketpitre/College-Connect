from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MarkIn(BaseModel):
    slot_id: str
    date: date
    absent: list[str] = Field(default_factory=list, max_length=500)
    client_id: str | None = Field(
        None, max_length=64, description="Device-made id, so a retried offline save isn't doubled"
    )
    base_version: int | None = Field(
        None, description="Version the device edited; a newer one on the server is a conflict"
    )


class EditRequestIn(BaseModel):
    slot_id: str
    date: date
    absent: list[str] = Field(default_factory=list, max_length=500)
    reason: str = Field(..., min_length=5, max_length=300)


class DecideIn(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)


class ExemptionIn(BaseModel):
    student_id: str
    kind: Literal["medical", "official_duty"]
    from_date: date
    to_date: date
    reason: str = Field(..., min_length=3, max_length=300)

    @model_validator(mode="after")
    def _dates(self) -> "ExemptionIn":
        if self.to_date < self.from_date:
            raise ValueError("to_date: The end date must be on or after the start date.")
        if (self.to_date - self.from_date).days > 120:
            raise ValueError("to_date: An exemption can cover at most 120 days.")
        return self
