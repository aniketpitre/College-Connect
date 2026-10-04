"""
Application settings, read from environment variables.

Locally they come from backend/.env (gitignored); on Vercel from Project Settings ->
Environment Variables. Values that tests or operators may change at runtime (such as
ADMIN_TOKEN) are read where they are used, not cached here.
"""

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

try:  # local dev only; python-dotenv never overrides variables that are already set
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    app_name: str
    mongodb_uri: str | None
    mongodb_db: str
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name="CollegeConnect",
            mongodb_uri=os.getenv("MONGODB_URI") or None,
            mongodb_db=os.getenv("MONGODB_DB", "collegeconnect"),
            allowed_origins=tuple(o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()),
        )


settings = Settings.from_env()
