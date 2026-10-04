"""Fee request bodies. Every amount is integer paise (₹1 = 100)."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Paise = Field(..., ge=0, le=10**11)  # up to ₹100 crore
PositivePaise = Field(..., gt=0, le=10**11)
Mode = Literal["cash", "upi", "card", "cheque", "dd", "bank_transfer"]


class FeeHeadIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(..., min_length=2, max_length=80)

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class FeeHeadUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    status: Literal["active", "archived"] | None = None


class StructureItem(BaseModel):
    head_id: str
    amount: int = Paise


class Installment(BaseModel):
    label: str = Field(..., min_length=1, max_length=40)
    due_date: date
    amount: int = PositivePaise


class StructureFields(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    items: list[StructureItem] = Field(..., min_length=1, max_length=30)
    installments: list[Installment] = Field(..., min_length=1, max_length=12)
    late_fee: int = Field(0, ge=0, le=10**9, description="Charged once per overdue installment")

    @model_validator(mode="after")
    def _check(self) -> "StructureFields":
        heads = [i.head_id for i in self.items]
        if len(set(heads)) != len(heads):
            raise ValueError("items: Each fee head appears once.")
        total = sum(i.amount for i in self.items)
        if total <= 0:
            raise ValueError("items: The total must be more than zero.")
        if sum(i.amount for i in self.installments) != total:
            raise ValueError("installments: Installments must add up to the total fee.")
        dates = [i.due_date for i in self.installments]
        if dates != sorted(dates):
            raise ValueError("installments: List installments in order of due date.")
        return self


class StructureIn(StructureFields):
    academic_year_id: str
    programme_id: str
    year_of_study: int = Field(..., ge=1, le=6)
    category_id: str | None = Field(None, description="Empty: applies to every category without its own structure")


class StructureUpdate(StructureFields):
    pass


class GenerateDemands(BaseModel):
    academic_year_id: str
    programme_id: str
    year_of_study: int = Field(..., ge=1, le=6)
    dry_run: bool = True


class ChargeIn(BaseModel):
    academic_year_id: str
    head_id: str
    amount: int = PositivePaise
    reason: str = Field(..., min_length=3, max_length=200)


class ConcessionIn(BaseModel):
    student_id: str
    academic_year_id: str
    head_id: str
    amount: int = PositivePaise
    kind: Literal["staff_ward", "sibling", "merit", "sports", "need_based", "other"]
    reason: str = Field(..., min_length=5, max_length=300)


class ScholarshipIn(BaseModel):
    student_id: str
    academic_year_id: str
    scheme: str = Field(..., min_length=2, max_length=80, description="e.g. MahaDBT Post-Matric, NSP")
    reference: str = Field("", max_length=80)
    expected: int = PositivePaise


class ScholarshipAction(BaseModel):
    action: Literal["sanction", "receive", "reject"]
    amount: int | None = Field(None, gt=0, le=10**11)
    reference: str | None = Field(None, max_length=80)
    reason: str | None = Field(None, max_length=300)


class CollectIn(BaseModel):
    student_id: str
    academic_year_id: str
    amount: int = PositivePaise
    mode: Mode
    reference: str = Field("", max_length=60, description="UPI ref, cheque/DD no., card slip, bank UTR")
    instrument_date: date | None = None
    bank: str = Field("", max_length=80)
    note: str = Field("", max_length=200)

    @model_validator(mode="after")
    def _reference(self) -> "CollectIn":
        if self.mode != "cash" and not self.reference.strip():
            raise ValueError("reference: Enter the reference number for this payment mode.")
        if self.mode in {"cheque", "dd"} and not self.bank.strip():
            raise ValueError("bank: Enter the bank name for a cheque or DD.")
        self.reference = re.sub(r"\s+", " ", self.reference.strip())
        return self


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=300)


class RefundRequest(BaseModel):
    student_id: str
    academic_year_id: str
    amount: int = PositivePaise
    mode: Mode
    reference: str = Field("", max_length=60)
    reason: str = Field(..., min_length=5, max_length=300)


class Decision(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)
