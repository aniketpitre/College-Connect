"""
Outgoing email.

With EMAIL_API_KEY set, mail is sent through Resend (https://resend.com). Without it,
messages are written to the log and kept in OUTBOX, so development and tests never
need a real provider.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass
class Email:
    to: str
    subject: str
    text: str


OUTBOX: list[Email] = []


def send_email(to: str, subject: str, text: str) -> bool:
    message = Email(to=to, subject=subject, text=text)
    if not settings.email_api_key:
        OUTBOX.append(message)
        del OUTBOX[:-50]
        log.info("Email (not sent: EMAIL_API_KEY unset) to=%s subject=%s\n%s", to, subject, text)
        return True
    try:
        res = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.email_api_key}"},
            json={"from": settings.email_from, "to": [to], "subject": subject, "text": text},
            timeout=10,
        )
        res.raise_for_status()
        return True
    except httpx.HTTPError:
        log.exception("Email to %s failed", to)
        return False
