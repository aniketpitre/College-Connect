import re

from pydantic import BaseModel, Field, field_validator


class NaacSettings(BaseModel):
    sanctioned_posts: int | None = Field(None, ge=0, le=2000, description="Sanctioned teaching posts")
    intake: dict[str, int] = Field(
        default_factory=dict,
        description="Sanctioned first-year intake by programme id, used when admissions aren't run here",
    )

    @field_validator("intake")
    @classmethod
    def _programme_ids(cls, v: dict[str, int]) -> dict[str, int]:
        # Keys become field names in MongoDB: only programme ids (24 hex characters) are allowed.
        if any(not re.fullmatch(r"[0-9a-f]{24}", k) or n < 0 for k, n in v.items()):
            raise ValueError("intake: Use programme ids and whole numbers.")
        return v
