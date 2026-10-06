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
from app.modules.deadlines import service as deadlines
from app.modules.grievance import service as grievance
from app.modules.knowledge import service as knowledge
from app.modules.library import service as library
from app.modules.mentoring import service as mentoring
from app.modules.messaging import reminders
from app.modules.messaging import service as messaging
from app.modules.notices import service as notices
from app.modules.payments import service as payments

router = APIRouter(tags=["jobs"], include_in_schema=False)


def check_secret(authorization: str | None) -> None:
    if not settings.cron_secret or authorization != f"Bearer {settings.cron_secret}":
        raise AppError(401, "Not allowed.", "unauthorized")


@router.get("/cron/daily")
def daily(authorization: str | None = Header(None)) -> dict[str, Any]:
    check_secret(authorization)
    out: dict[str, Any] = {
        "online_payments": payments.daily_check(),
        "attendance_alerts": stats.send_alerts(),
        "fee_reminders": reminders.queue_fee_reminders(),
        "certificates": certificates.escalate_overdue(),
        "library": library.daily(),
        "grievances": grievance.daily(),
        "early_warning": mentoring.daily(),
        "notice_translations": notices.translate_pending(),
        "knowledge_base": knowledge.catch_up(),
        "deadlines": deadlines.daily(),
    }
    out["messages"] = messaging.process_queue()  # what's left waits for tomorrow or "Send now"
    return out
