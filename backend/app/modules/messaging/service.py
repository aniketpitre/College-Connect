"""
Messages to students and parents (plan 3.3): email, SMS and WhatsApp.

`notify(student, key, params)` reaches the student and, for what the student shares (DPDP
consent, see parents.access), their linked parents. Each person gets the message on the
channels they keep switched on (all on by default) that the college has set up: email always
works; SMS (MSG91) and WhatsApp (Meta Cloud API) start working when their keys are set.

Bulk messages (results, fee reminders, attendance alerts) go into `message_queue` and are sent
by the daily job within a time budget (Vercel functions are short), or straight away by staff
from the delivery log page. Every attempt is written to `message_log`, which MongoDB empties
after 180 days to keep the free database small.
"""

import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.auth import AuthContext
from app.core.config import settings
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.modules.messaging import templates
from app.modules.setup import service as setup

register_indexes(
    "message_log",
    [
        IndexModel([("at", DESCENDING)], expireAfterSeconds=180 * 24 * 3600),
        IndexModel([("student_id", ASCENDING), ("at", DESCENDING)]),
    ],
)
register_indexes("message_queue", [IndexModel([("created_at", ASCENDING)])])

CHANNELS = ("email", "sms", "whatsapp")
CHANNEL_LABELS = {"email": "Email", "sms": "SMS", "whatsapp": "WhatsApp"}


# --- channels -------------------------------------------------------------------------------


def available() -> dict[str, bool]:
    return {
        "email": True,
        "sms": bool(settings.sms_api_key),
        "whatsapp": bool(settings.whatsapp_token and settings.whatsapp_phone_id),
    }


def _sms(phone: str, key: str, params: dict[str, Any]) -> None:
    template_id = os.getenv(f"SMS_TEMPLATE_{key.upper()}")
    if not template_id:
        raise RuntimeError(f"No DLT template id (SMS_TEMPLATE_{key.upper()})")
    values = {f"var{i + 1}": v for i, v in enumerate(templates.ordered(key, params))}
    res = httpx.post(
        "https://control.msg91.com/api/v5/flow/",
        headers={"authkey": settings.sms_api_key or ""},
        json={"template_id": template_id, "short_url": "0", "recipients": [{"mobiles": f"91{phone}", **values}]},
        timeout=10,
    )
    res.raise_for_status()


def _whatsapp(phone: str, key: str, language: str, params: dict[str, Any]) -> None:
    name = os.getenv(f"WHATSAPP_TEMPLATE_{key.upper()}")
    if not name:
        raise RuntimeError(f"No approved template (WHATSAPP_TEMPLATE_{key.upper()})")
    res = httpx.post(
        f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_id}/messages",
        headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": f"91{phone}",
            "type": "template",
            "template": {
                "name": name,
                "language": {"code": language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": v} for v in templates.ordered(key, params)],
                    }
                ],
            },
        },
        timeout=10,
    )
    res.raise_for_status()


def _mask(to: str) -> str:
    if "@" in to:
        name, _, domain = to.partition("@")
        return f"{name[:2]}•••@{domain}"
    return f"••••••{to[-4:]}"


def preferences(user: dict[str, Any]) -> dict[str, bool]:
    saved = user.get("notify") or {}
    return {c: bool(saved.get(c, True)) for c in CHANNELS}


def _addresses(user: dict[str, Any], student: dict[str, Any] | None) -> dict[str, str | None]:
    """Where this person can be reached: their account first, then the student record."""
    own_student = student if student and student.get("user_id") == user["_id"] else None
    email = user.get("email") or user.get("contact_email") or (own_student or {}).get("email")
    phone = user.get("phone") or (own_student or {}).get("phone")
    return {"email": email, "sms": phone, "whatsapp": phone}


def send_to(
    user: dict[str, Any],
    key: str,
    params: dict[str, Any],
    *,
    student: dict[str, Any] | None = None,
    channels: tuple[str, ...] | None = None,
) -> int:
    """Sends one message to one person on their channels; returns how many went out."""
    db = get_db()
    language = user.get("language") or "en"
    subject, text = templates.render(key, language, params)
    on = preferences(user)
    ready = available()
    addresses = _addresses(user, student)
    college = setup.institution().get("name") or "CollegeConnect"
    sent = 0
    for channel in channels or CHANNELS:
        to = addresses.get(channel)
        if not (to and ready[channel] and (on[channel] or key == "otp")):
            continue
        error = None
        try:
            if channel == "email":
                if not send_email(to, subject, f"{text}\n\n{college}\n"):
                    error = "Email service refused the message"
            elif channel == "sms":
                _sms(to, key, params)
            else:
                _whatsapp(to, key, language, params)
        except (httpx.HTTPError, RuntimeError) as e:
            error = str(e)[:200]
        db.message_log.insert_one(
            {
                "at": datetime.now(UTC),
                "user_id": user["_id"],
                "student_id": student["_id"] if student else None,
                "template": key,
                "channel": channel,
                "to": _mask(to),
                "status": "failed" if error else "sent",
                **({"error": error} if error else {}),
            }
        )
        if not error:
            sent += 1
    return sent


def recipients(student: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """The student's account and the linked parents who may see this kind of message."""
    from app.modules.parents import service as parents

    db = get_db()
    people = []
    user = db.users.find_one({"_id": student.get("user_id"), "status": {"$ne": "disabled"}})
    if user and not user.get("read_only"):
        people.append(user)
    area = templates.AREA[key]
    if area is None or parents.access(student)[area]:
        people += list(db.users.find({"kind": "parent", "status": "active", "children.student_id": student["_id"]}))
    return people


def notify(student: dict[str, Any], key: str, params: dict[str, Any]) -> int:
    full = {"student": student["name"], **params}
    return sum(send_to(u, key, full, student=student) for u in recipients(student, key))


def queue(student_id: ObjectId, key: str, params: dict[str, Any]) -> None:
    get_db().message_queue.insert_one(
        {"student_id": student_id, "template": key, "params": params, "created_at": datetime.now(UTC)}
    )


def process_queue(budget_seconds: float = 8.0, limit: int = 500) -> dict[str, int]:
    """Sends queued messages until the time budget runs out; the rest wait for the next run."""
    db = get_db()
    started = time.monotonic()
    done = sent = 0
    while done < limit and time.monotonic() - started < budget_seconds:
        item = db.message_queue.find_one_and_delete({}, sort=[("created_at", ASCENDING)])
        if item is None:
            break
        done += 1
        student = db.students.find_one({"_id": item["student_id"]})
        if student:
            sent += notify(student, item["template"], item["params"])
    return {"processed": done, "sent": sent, "waiting": db.message_queue.count_documents({})}


# --- people's own settings ------------------------------------------------------------------


def my_settings(ctx: AuthContext) -> dict[str, Any]:
    on = preferences(ctx.user)
    ready = available()
    addresses = _addresses(ctx.user, None)
    if ctx.user.get("kind") == "student":
        s = get_db().students.find_one({"user_id": ctx.user_id}, {"email": 1, "phone": 1, "user_id": 1})
        addresses = _addresses(ctx.user, s)
    return {
        "channels": [
            {
                "channel": c,
                "label": CHANNEL_LABELS[c],
                "on": on[c],
                "available": ready[c],
                "to": _mask(to) if (to := addresses[c]) else None,
            }
            for c in CHANNELS
        ]
    }


def set_settings(ctx: AuthContext, values: dict[str, bool]) -> dict[str, Any]:
    if not any(values.get(c, True) for c in CHANNELS):
        raise AppError(422, "Keep at least one way for the college to reach you.", "no_channel")
    get_db().users.update_one(
        {"_id": ctx.user_id}, {"$set": {"notify": {c: bool(values.get(c, True)) for c in CHANNELS}}}
    )
    ctx.user["notify"] = values
    return my_settings(ctx)


# --- staff: the delivery log ----------------------------------------------------------------


def log(*, template: str | None, status: str | None, student_id: str | None, limit: int = 200) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {}
    if template:
        query["template"] = template
    if status:
        query["status"] = status
    if student_id:
        try:
            query["student_id"] = ObjectId(student_id)
        except Exception as e:  # noqa: BLE001
            raise AppError(404, "Student not found.") from e
    rows = list(db.message_log.find(query).sort("at", DESCENDING).limit(limit))
    names = {
        u["_id"]: u["name"] for u in db.users.find({"_id": {"$in": list({r["user_id"] for r in rows})}}, {"name": 1})
    }
    return {
        "available": available(),
        "waiting": db.message_queue.count_documents({}),
        "templates": templates.LABELS,
        "messages": [
            {
                "at": r["at"].isoformat(),
                "to_name": names.get(r["user_id"], "?"),
                "to": r["to"],
                "template": r["template"],
                "template_label": templates.LABELS.get(r["template"], r["template"]),
                "channel": r["channel"],
                "status": r["status"],
                "error": r.get("error"),
                "student_id": str(r["student_id"]) if r.get("student_id") else None,
            }
            for r in rows
        ],
    }
