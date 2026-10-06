from typing import Literal

from pydantic import BaseModel, Field

from app.modules.students.schemas import DocumentType


class SchemeIn(BaseModel):
    code: str = Field(..., pattern=r"^[a-z0-9-]{3,40}$")
    name: str = Field(..., min_length=3, max_length=160)
    portal: Literal["MahaDBT", "NSP", "Other"] = "MahaDBT"
    link: str | None = Field(None, max_length=300)
    categories: list[str] = Field(default_factory=list, description="Category codes; empty for any category")
    income_limit: int | None = Field(None, ge=0, le=10**8, description="Family income a year, rupees")
    min_attendance: float | None = Field(None, ge=0, le=100)
    min_previous_percentage: float | None = Field(None, ge=0, le=100)
    gender: Literal["any", "female"] = "any"
    domicile: str | None = Field(None, max_length=60, description="State the student must belong to")
    years: list[int] = Field(default_factory=list, description="Years of study; empty for any")
    documents: list[DocumentType] = Field(default_factory=list)
    note: str | None = Field(None, max_length=500)
    active: bool = True


class IncomeIn(BaseModel):
    family_income: int = Field(..., ge=0, le=10**8, description="Rupees a year, as on the income certificate")
