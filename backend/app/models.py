from typing import Literal
from pydantic import BaseModel, Field

Language = Literal["en", "hi", "mr"]
Category = Literal["admissions", "fees", "examinations", "placements", "hostel", "notices"]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    language: Language = "en"
    category: Category | None = None


class SourceRef(BaseModel):
    title: str
    document: str
    section: str


class QueryResponse(BaseModel):
    answer: str
    language: Language
    category: Category
    sources: list[SourceRef]
    confidence: float
    grounded: bool


class CategoryInfo(BaseModel):
    id: Category
    label_en: str
    label_hi: str
    label_mr: str
