from pydantic import BaseModel, Field, field_validator


def _isbn(v: str | None) -> str | None:
    if not v:
        return None
    digits = "".join(c for c in v if c.isdigit() or c in "Xx").upper()
    if len(digits) not in (10, 13):
        raise ValueError("An ISBN has 10 or 13 digits.")
    return digits


class BookIn(BaseModel):
    isbn: str | None = None
    title: str = Field(..., min_length=1, max_length=200)
    authors: list[str] = Field(default_factory=list, max_length=10)
    publisher: str = Field("", max_length=120)
    year: int | None = Field(None, ge=1800, le=2100)
    subject: str = Field("", max_length=80)
    copies: int = Field(1, ge=0, le=200)
    barcodes: list[str] = Field(default_factory=list, max_length=200, description="Leave empty to number them")

    _isbn = field_validator("isbn")(_isbn)


class CopiesIn(BaseModel):
    count: int = Field(1, ge=1, le=200)
    barcodes: list[str] = Field(default_factory=list, max_length=200)


class IssueIn(BaseModel):
    barcode: str = Field(..., min_length=1, max_length=40)
    prn: str = Field(..., min_length=1, max_length=40)


class ReturnIn(BaseModel):
    barcode: str = Field(..., min_length=1, max_length=40)


class LostIn(BaseModel):
    price: int = Field(..., ge=0, le=10**8, description="Paise, charged to the student")


class SettingsIn(BaseModel):
    loan_days: int = Field(14, ge=1, le=180)
    max_books: int = Field(3, ge=1, le=20)
    fine_per_day: int = Field(200, ge=0, le=10**6, description="Paise")
    max_renewals: int = Field(1, ge=0, le=5)
    hold_days: int = Field(2, ge=1, le=14)


class ReserveIn(BaseModel):
    book_id: str
