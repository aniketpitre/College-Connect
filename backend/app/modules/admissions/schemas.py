from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.modules.fees.schemas import Mode
from app.modules.students.schemas import DocumentType, PersonalFields, clean_phone

DEFAULT_DOCUMENTS: tuple[DocumentType, ...] = ("ssc_marksheet", "hsc_marksheet")
EnquirySource = Literal["walk_in", "phone", "website", "help_desk", "other"]
EnquiryStatus = Literal["new", "contacted", "applied", "closed"]


class ProgrammeSeats(BaseModel):
    programme_id: str
    year_of_study: int = Field(1, ge=1, le=6)
    seats: int = Field(..., ge=1, le=5000)
    # Seats kept for each reserved category ({category_id: seats}); the rest are open to all.
    reserved: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fits(self) -> "ProgrammeSeats":
        if any(n < 0 for n in self.reserved.values()) or sum(self.reserved.values()) > self.seats:
            raise ValueError("reserved: Reserved seats can't be more than the total seats.")
        return self


class RefundRule(BaseModel):
    """Cancelled `days_before` or more days before the course starts → `percent` of the fees paid back."""

    days_before: int = Field(..., ge=-365, le=365)
    percent: int = Field(..., ge=0, le=100)


class CycleIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    academic_year_id: str
    apply_until: date
    course_start: date
    application_fee: int = Field(0, ge=0, le=10**8, description="Paise")
    programmes: list[ProgrammeSeats] = Field(..., min_length=1)
    documents: list[DocumentType] = Field(default_factory=lambda: list(DEFAULT_DOCUMENTS))
    refund_rules: list[RefundRule] = Field(
        default_factory=lambda: [RefundRule(days_before=0, percent=100), RefundRule(days_before=-15, percent=80)]
    )
    processing_fee: int = Field(100_000, ge=0, le=10**7, description="Kept from every refund, in paise")


class CycleUpdate(CycleIn):
    status: Literal["draft", "open", "closed"]


class EnquiryIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    phone: str
    email: EmailStr | None = None
    programme_id: str | None = None
    message: str = Field("", max_length=500)

    _phone = field_validator("phone")(clean_phone)


class StaffEnquiryIn(EnquiryIn):
    source: EnquirySource = "walk_in"
    follow_up_on: date | None = None


class EnquiryUpdate(BaseModel):
    status: EnquiryStatus | None = None
    follow_up_on: date | None = None
    note: str = Field("", max_length=500)


class StartIn(BaseModel):
    """A new applicant: name and contact, then a sign-in code."""

    cycle_id: str
    name: str = Field(..., min_length=2, max_length=120)
    phone: str
    email: EmailStr

    _phone = field_validator("phone")(clean_phone)


class PhoneIn(BaseModel):
    phone: str

    _phone = field_validator("phone")(clean_phone)


class CodeIn(PhoneIn):
    code: str = Field(..., pattern=r"^\d{6}$")


class ApplicationIn(PersonalFields):
    """What the applicant fills in (all optional while it is a draft)."""

    programme_id: str | None = None
    year_of_study: int = Field(1, ge=1, le=6)


class Decision(BaseModel):
    action: Literal["verify", "return", "reject"]
    reason: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def _reason(self) -> "Decision":
        if self.action != "verify" and not (self.reason or "").strip():
            raise ValueError("reason: Say what needs fixing, or why it is rejected.")
        return self


class DocumentDecision(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)


class FeeIn(BaseModel):
    """The application fee paid at the counter (or waived)."""

    mode: Mode | Literal["waived"]
    reference: str = Field("", max_length=60)


class RoundIn(BaseModel):
    programme_id: str
    accept_by: date
    dry_run: bool = True


class ConfirmIn(BaseModel):
    division_id: str | None = None
    prn: str | None = Field(None, description="Leave empty to number it automatically")
    roll_no: str | None = Field(None, max_length=20)
    admission_date: date | None = None


class CancelIn(BaseModel):
    reason: str = Field(..., min_length=5, max_length=300)
