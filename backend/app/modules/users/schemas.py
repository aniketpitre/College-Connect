import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.rbac import STAFF_ROLES

PRN_PATTERN = re.compile(r"^[A-Z0-9/-]{4,20}$")


class UserCreate(BaseModel):
    kind: Literal["staff", "student"]
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr | None = None
    prn: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    roles: list[str] = Field(default_factory=list)
    department_id: str | None = Field(None, description="Staff: their department (HOD/faculty scope)")

    @field_validator("prn")
    @classmethod
    def _prn(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not PRN_PATTERN.match(value):
            raise ValueError("PRN may contain only letters, digits, / and - (4-20 characters)")
        return value

    @model_validator(mode="after")
    def _by_kind(self) -> "UserCreate":
        if self.kind == "staff":
            if not self.email:
                raise ValueError("Staff accounts need an email address")
            if not self.roles:
                raise ValueError("Choose at least one role")
            invalid = [r for r in self.roles if r not in STAFF_ROLES]
            if invalid:
                raise ValueError(f"Not a staff role: {', '.join(invalid)}")
            self.roles = sorted(set(self.roles))
        else:
            if not self.prn:
                raise ValueError("Student accounts need a PRN")
            self.roles = ["student"]
        return self


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    roles: list[str] | None = None
    department_id: str | None = Field(None, description='"" removes the department')
    status: Literal["active", "disabled"] | None = None
    reason: str | None = Field(default=None, max_length=300)


class ReasonBody(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
