from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Translation(BaseModel):
    title: str = Field("", max_length=200)
    body: str = Field("", max_length=20_000)


class Audience(BaseModel):
    kind: Literal["everyone", "students", "staff", "class"]
    programme_id: str | None = None
    year_of_study: int | None = Field(None, ge=1, le=6)
    division_id: str | None = None

    @model_validator(mode="after")
    def _class(self) -> "Audience":
        if self.kind == "class" and not self.programme_id:
            raise ValueError("programme_id: Choose the programme.")
        if self.kind != "class":
            self.programme_id = self.year_of_study = self.division_id = None
        if self.division_id and not self.year_of_study:
            raise ValueError("year_of_study: Choose the year for a division.")
        return self


class NoticeIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field("", max_length=20_000)
    hi: Translation | None = None
    mr: Translation | None = None
    audience: Audience
    publish_at: datetime | None = Field(None, description="Default: now")
    expires_on: date | None = None
    pinned: bool = False


class NoticeUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    body: str | None = Field(None, max_length=20_000)
    hi: Translation | None = None
    mr: Translation | None = None
    expires_on: date | None = None
    pinned: bool | None = None
    status: Literal["published", "withdrawn"] | None = None
    reason: str | None = Field(None, max_length=300)
