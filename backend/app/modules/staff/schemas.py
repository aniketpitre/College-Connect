from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Qualification(BaseModel):
    level: Literal["ug", "pg", "mphil", "phd", "net", "set", "other"]
    degree: str = Field(..., min_length=1, max_length=80, description="e.g. M.Sc. Computer Science, NET (UGC)")
    university: str | None = Field(None, max_length=120)
    year: int | None = Field(None, ge=1950, le=2100)


class StaffProfileIn(BaseModel):
    employee_code: str | None = Field(None, max_length=20)
    designation: str = Field(..., min_length=2, max_length=80)
    employment: Literal["permanent", "contract", "visiting", "ad_hoc"] = "permanent"
    teaching: bool = True
    joined_on: date | None = None
    experience_years: float = Field(0, ge=0, le=60, description="Before joining this college")
    phone: str | None = Field(None, max_length=15)
    qualifications: list[Qualification] = Field(default_factory=list, max_length=15)
    appointment_order: str | None = Field(None, max_length=60)
    appointment_date: date | None = None
    university_approved: bool = False
    left_on: date | None = None


class LeaveType(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z]{2,5}$")
    name: str = Field(..., min_length=2, max_length=40)
    days: float | None = Field(None, ge=0, le=365, description="A year; empty for no limit (on duty, without pay)")
    half_day: bool = True


class LeaveSettings(BaseModel):
    types: list[LeaveType] = Field(..., min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_codes(self) -> "LeaveSettings":
        codes = [t.code for t in self.types]
        if len(codes) != len(set(codes)):
            raise ValueError("types: Each leave type needs its own code.")
        return self


class LeaveIn(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z]{2,5}$")
    from_date: date
    to_date: date
    half_day: bool = False
    reason: str = Field(..., min_length=3, max_length=300)

    @model_validator(mode="after")
    def check_dates(self) -> "LeaveIn":
        if self.to_date < self.from_date:
            raise ValueError("to_date: The last day can't be before the first day.")
        if self.half_day and self.to_date != self.from_date:
            raise ValueError("half_day: A half day is for a single date.")
        if (self.to_date - self.from_date).days > 90:
            raise ValueError("to_date: Apply for at most 90 days at a time.")
        return self


class DecideIn(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=300)


class AdjustIn(BaseModel):
    user_id: str
    code: str = Field(..., pattern=r"^[A-Z]{2,5}$")
    days: float = Field(..., ge=-90, le=90)
    reason: str = Field(..., min_length=3, max_length=200)
