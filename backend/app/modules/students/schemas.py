"""Student master record (spec §3.3). Dates are ISO strings (YYYY-MM-DD)."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

PRN_PATTERN = r"^[A-Z0-9/-]{4,20}$"
Gender = Literal["female", "male", "other"]
StudentStatus = Literal["active", "tc", "graduated", "dropped", "detained"]
DOCUMENT_TYPES = (
    "ssc_marksheet",
    "hsc_marksheet",
    "leaving_certificate",
    "caste_certificate",
    "income_certificate",
    "domicile_certificate",
    "aadhaar_masked",
    "gap_certificate",
    "other",
)
DocumentType = Literal[
    "ssc_marksheet",
    "hsc_marksheet",
    "leaving_certificate",
    "caste_certificate",
    "income_certificate",
    "domicile_certificate",
    "aadhaar_masked",
    "gap_certificate",
    "other",
]


def clean_phone(v: str | None) -> str | None:
    """Indian mobile numbers: 10 digits starting 6–9; +91 / 0 prefixes are removed."""
    if v is None or not v.strip():
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("Enter a 10-digit mobile number.")
    return digits


def aadhaar_last4(v: str | None) -> str | None:
    """Only the last 4 digits of Aadhaar are ever stored (spec §4.2)."""
    if v is None or not v.strip():
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 4:
        return digits
    if len(digits) != 12 or digits[0] in "01":
        raise ValueError("Enter the 12-digit Aadhaar number (only the last 4 digits are kept).")
    return digits[-4:]


class Address(BaseModel):
    line: str = Field("", max_length=200)
    city: str = Field("", max_length=80)
    district: str = Field("", max_length=80)
    state: str = Field("Maharashtra", max_length=80)
    pincode: str = Field("", pattern=r"^(\d{6})?$")


class Guardian(BaseModel):
    name: str = Field("", max_length=120)
    relation: str = Field("", max_length=40)
    phone: str | None = None
    email: EmailStr | None = None

    _phone = field_validator("phone")(clean_phone)


class PreviousEducation(BaseModel):
    exam: str = Field("", max_length=40, description="e.g. HSC")
    board: str = Field("", max_length=120)
    year: int | None = Field(None, ge=1980, le=2100)
    percentage: float | None = Field(None, ge=0, le=100)


class PersonalFields(BaseModel):
    """Fields a student may ask to correct (and the office may edit)."""

    name: str | None = Field(None, min_length=2, max_length=120)
    mother_name: str | None = Field(None, max_length=120)
    gender: Gender | None = None
    dob: date | None = None
    email: EmailStr | None = None
    phone: str | None = None
    category_id: str | None = None
    apaar_id: str | None = Field(None, pattern=r"^(\d{12})?$", description="ABC / APAAR ID, 12 digits")
    address: Address | None = None
    guardian: Guardian | None = None
    previous_education: PreviousEducation | None = None

    _phone = field_validator("phone")(clean_phone)

    @field_validator("dob")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        if v and not (date(1940, 1, 1) <= v <= date.today()):
            raise ValueError("Enter a valid date of birth.")
        return v


class StudentUpdate(PersonalFields):
    """Office edits: personal fields plus placement, status and Aadhaar."""

    aadhaar: str | None = Field(None, description="12 digits; only the last 4 are stored")
    programme_id: str | None = None
    year_of_study: int | None = Field(None, ge=1, le=6)
    division_id: str | None = None
    roll_no: str | None = Field(None, max_length=20)
    admission_date: date | None = None
    status: StudentStatus | None = None
    guardian_consent: bool | None = Field(None, description="Parental consent recorded (under-18 students)")
    reason: str | None = Field(None, max_length=300)

    _aadhaar = field_validator("aadhaar")(aadhaar_last4)


class StudentCreate(StudentUpdate):
    prn: str = Field(..., description="Permanent registration number; the student signs in with it")
    name: str = Field(..., min_length=2, max_length=120)
    programme_id: str
    year_of_study: int = Field(..., ge=1, le=6)

    @field_validator("prn")
    @classmethod
    def _prn(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(PRN_PATTERN, v):
            raise ValueError("Use 4–20 letters, digits, / or - for the PRN.")
        return v


class ChangeRequestIn(BaseModel):
    changes: PersonalFields
    reason: str = Field(..., min_length=5, max_length=300)


class Decision(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)


class DocumentDecision(BaseModel):
    verified: bool
    reason: str | None = Field(None, max_length=300)
