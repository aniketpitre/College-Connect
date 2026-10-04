"""Request bodies for institution setup. Dates are ISO strings (YYYY-MM-DD)."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Code = Field(..., min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._&/-]*$")
Name = Field(..., min_length=2, max_length=120)
Status = Literal["active", "archived"]


def _upper(v: str) -> str:
    return re.sub(r"\s+", " ", v.strip()).upper()


class InstitutionSettings(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    short_name: str = Field("", max_length=40)
    address: str = Field("", max_length=400)
    phone: str = Field("", max_length=40)
    email: EmailStr | None = None
    website: str = Field("", max_length=200)
    university: str = Field("", max_length=200)
    college_code: str = Field("", max_length=40, description="University / AISHE code")
    receipt_prefix: str = Field("R", min_length=1, max_length=6, pattern=r"^[A-Z]+$")
    certificate_prefix: str = Field("C", min_length=1, max_length=6, pattern=r"^[A-Z]+$")


class AcademicYearIn(BaseModel):
    name: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="e.g. 2026-27")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check(self) -> "AcademicYearIn":
        first, second = int(self.name[:4]), int(self.name[5:])
        if (first + 1) % 100 != second:
            raise ValueError("name: The second year must follow the first, e.g. 2026-27.")
        if self.end_date <= self.start_date:
            raise ValueError("end_date: The end date must be after the start date.")
        return self


class AcademicYearUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    status: Status | None = None


class DepartmentIn(BaseModel):
    code: str = Code
    name: str = Name

    _norm = field_validator("code")(_upper)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    status: Status | None = None


class ProgrammeIn(BaseModel):
    code: str = Code
    name: str = Name
    department_id: str
    level: Literal["UG", "PG", "Diploma"] = "UG"
    duration_years: int = Field(3, ge=1, le=6)
    semesters_per_year: int = Field(2, ge=1, le=3)
    year_labels: list[str] = Field(default_factory=list, description="e.g. FY, SY, TY")

    _norm = field_validator("code")(_upper)

    @model_validator(mode="after")
    def _labels(self) -> "ProgrammeIn":
        labels = [x.strip().upper() for x in self.year_labels if x.strip()]
        if not labels:
            defaults = ["FY", "SY", "TY", "4Y", "5Y", "6Y"]
            labels = defaults[: self.duration_years]
        if len(labels) != self.duration_years:
            raise ValueError("year_labels: Give one label per year of the programme.")
        self.year_labels = labels
        return self


class ProgrammeUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    department_id: str | None = None
    year_labels: list[str] | None = None
    status: Status | None = None


class DivisionIn(BaseModel):
    programme_id: str
    year_of_study: int = Field(..., ge=1, le=6)
    name: str = Field(..., min_length=1, max_length=10)
    capacity: int | None = Field(None, ge=1, le=500)

    _norm = field_validator("name")(_upper)


class DivisionUpdate(BaseModel):
    capacity: int | None = Field(None, ge=1, le=500)
    status: Status | None = None


class SubjectIn(BaseModel):
    programme_id: str
    semester: int = Field(..., ge=1, le=18)
    code: str = Code
    name: str = Name
    credits: int = Field(..., ge=0, le=20)
    type: Literal["theory", "practical", "project"] = "theory"
    max_internal: int = Field(..., ge=0, le=500)
    max_external: int = Field(..., ge=0, le=500)

    _norm = field_validator("code")(_upper)


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    credits: int | None = Field(None, ge=0, le=20)
    type: Literal["theory", "practical", "project"] | None = None
    max_internal: int | None = Field(None, ge=0, le=500)
    max_external: int | None = Field(None, ge=0, le=500)
    status: Status | None = None


class CategoryIn(BaseModel):
    code: str = Code
    name: str = Name
    reserved_percent: float | None = Field(None, ge=0, le=100)

    _norm = field_validator("code")(_upper)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    reserved_percent: float | None = Field(None, ge=0, le=100)
    status: Status | None = None


class HolidayIn(BaseModel):
    academic_year_id: str
    date: date
    name: str = Field(..., min_length=2, max_length=120)


class HolidayUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    status: Status | None = None
