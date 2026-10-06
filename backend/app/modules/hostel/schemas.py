from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BlockIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    gender: Literal["boys", "girls", "any"] = "any"
    annual_fee: int = Field(0, ge=0, le=10**8, description="Paise, charged when a bed is allotted")


class RoomsIn(BaseModel):
    numbers: list[str] = Field(..., min_length=1, max_length=200)
    beds: int = Field(2, ge=1, le=20)


class AllotIn(BaseModel):
    prn: str = Field(..., min_length=1, max_length=40)
    room_id: str
    bed: int | None = Field(None, ge=1, le=20)


class VacateIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=200)


class OutpassIn(BaseModel):
    leave_at: datetime
    return_by: datetime
    destination: str = Field(..., min_length=2, max_length=120)
    reason: str = Field(..., min_length=3, max_length=300)

    @model_validator(mode="after")
    def _order(self) -> "OutpassIn":
        if self.return_by <= self.leave_at:
            raise ValueError("return_by: The return time must be after leaving.")
        return self


class OutpassAction(BaseModel):
    action: Literal["approve", "reject", "out", "returned", "cancel"]
    reason: str | None = Field(None, max_length=200)


class ComplaintIn(BaseModel):
    category: Literal["room", "water", "electricity", "cleaning", "mess", "other"]
    text: str = Field(..., min_length=5, max_length=1000)


class ComplaintUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    note: str = Field("", max_length=300)


class MessMenu(BaseModel):
    days: dict[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], str] = Field(default_factory=dict)
