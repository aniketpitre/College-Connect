from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.students.schemas import clean_phone


class ParentLink(BaseModel):
    """The office links a parent (found or created by mobile number) to a student."""

    name: str = Field(..., min_length=2, max_length=120)
    phone: str
    email: EmailStr | None = None
    relation: str = Field("Parent", min_length=2, max_length=40)
    consent: bool = Field(False, description="Parental consent recorded (needed for students under 18)")

    _phone = field_validator("phone")(clean_phone)


class Access(BaseModel):
    """What an adult student shares with their parents."""

    fees: bool
    attendance: bool
    results: bool


class CodeRequest(BaseModel):
    phone: str

    _phone = field_validator("phone")(clean_phone)


class CodeVerify(BaseModel):
    phone: str
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

    _phone = field_validator("phone")(clean_phone)
