from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "academic", "examination", "fees", "infrastructure", "library", "hostel", "ragging", "harassment", "other"
]


class GrievanceIn(BaseModel):
    category: Category
    subject: str = Field(..., min_length=3, max_length=120)
    text: str = Field(..., min_length=10, max_length=3000)
    anonymous: bool = False


class CommentIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class FeedbackIn(BaseModel):
    satisfied: bool
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)


class ActionIn(BaseModel):
    action: Literal["take", "reply", "note", "resolve"]
    text: str | None = Field(None, max_length=3000)


class SlaSettings(BaseModel):
    sla_days: dict[Category, int] = Field(..., description="Working days to resolve, per category")
    close_after_days: int = Field(7, ge=1, le=60, description="Resolved cases close by themselves after this")
