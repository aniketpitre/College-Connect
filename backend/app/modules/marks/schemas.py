from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ComponentIn(BaseModel):
    key: str | None = Field(None, max_length=10, description="Kept when editing; new components get one")
    name: str = Field(..., min_length=2, max_length=60)
    max: float = Field(..., gt=0, le=500)
    held_on: date | None = Field(None, description="Test date; used to flag absent-but-marked students")


class SchemeIn(BaseModel):
    subject_id: str
    academic_year_id: str | None = None
    components: list[ComponentIn] = Field(..., min_length=1, max_length=12)
    deadline: date | None = Field(None, description="Last day for marks entry (Exam Cell)")


class SheetSave(BaseModel):
    division_id: str
    subject_id: str
    marks: dict[str, dict[str, float | Literal["AB"] | None]] = Field(default_factory=dict)
    base_version: int = 0


class SheetAction(BaseModel):
    division_id: str
    subject_id: str
    action: Literal["publish", "approve", "return", "lock", "unlock"]
    reason: str | None = Field(None, max_length=300)
