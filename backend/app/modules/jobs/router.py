"""
Scheduled work. Vercel Hobby runs cron jobs at most once a day, so one daily job does
everything that needs a schedule (vercel.json → GET /api/v1/cron/daily, 9:00 IST).
"""

from typing import Any

from fastapi import APIRouter, Header

from app.core.config import settings
from app.core.errors import AppError
from app.modules.attendance import stats
from app.modules.certificates import service as certificates
from app.modules.payments import service as payments

router = APIRouter(tags=["jobs"], include_in_schema=False)


def check_secret(authorization: str | None) -> None:
    if not settings.cron_secret or authorization != f"Bearer {settings.cron_secret}":
        raise AppError(401, "Not allowed.", "unauthorized")


@router.get("/cron/daily")
def daily(authorization: str | None = Header(None)) -> dict[str, Any]:
    check_secret(authorization)
    return {
        "attendance_alerts": stats.send_alerts(),
        "certificates": certificates.escalate_overdue(),
        "online_payments": payments.daily_check(),
    }
