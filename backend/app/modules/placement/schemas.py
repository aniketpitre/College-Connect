from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Eligibility(BaseModel):
    programme_ids: list[str] = Field(default_factory=list, description="Empty: every programme")
    years: list[int] = Field(default_factory=list, description="Years of study, e.g. [3]; empty: any")
    min_cgpa: float | None = Field(None, ge=0, le=10)
    max_backlogs: int | None = Field(None, ge=0, le=50)


class DriveIn(BaseModel):
    company: str = Field(..., min_length=2, max_length=120)
    role: str = Field(..., min_length=2, max_length=120)
    ctc_lpa: float = Field(..., ge=0, le=500, description="Package, lakh per year")
    location: str = Field("", max_length=120)
    description: str = Field("", max_length=2000)
    register_by: date
    drive_date: date | None = None
    rounds: list[str] = Field(default_factory=lambda: ["Aptitude test", "Interview"], min_length=1, max_length=8)
    eligibility: Eligibility = Field(default_factory=lambda: Eligibility(min_cgpa=None, max_backlogs=None))
    status: Literal["open", "closed", "completed"] = "open"


class ProfileIn(BaseModel):
    skills: str = Field("", max_length=500)
    linkedin: str = Field("", max_length=200)


class ResultIn(BaseModel):
    registration_ids: list[str] = Field(..., min_length=1, max_length=500)
    action: Literal["next", "reject", "select"]
    ctc_lpa: float | None = Field(None, ge=0, le=500)
