from pydantic import BaseModel, Field


class NaacSettings(BaseModel):
    sanctioned_posts: int | None = Field(None, ge=0, le=2000, description="Sanctioned teaching posts")
    intake: dict[str, int] = Field(
        default_factory=dict,
        description="Sanctioned first-year intake by programme id, used when admissions aren't run here",
    )
