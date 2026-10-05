"""The college works in Indian time; the server (Vercel) runs in UTC."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    """Today's date in India (differs from the UTC date between midnight and 5:30 am IST)."""
    return now().astimezone(IST).date()
