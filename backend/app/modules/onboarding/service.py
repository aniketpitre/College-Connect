"""
First sign-in for students (spec R13): confirm contact details, accept the privacy notice,
choose a language. Consent is recorded with the notice version (DPDP Act 2023), so a new
version of the notice can ask again.
"""

from datetime import UTC, date, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.modules.students import service as students

PRIVACY_VERSION = "2026-10"

register_indexes("consents", [IndexModel([("user_id", ASCENDING), ("accepted_at", DESCENDING)])])


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    born = date.fromisoformat(dob)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def status(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    age = _age(student.get("dob"))
    return {
        "privacy_version": PRIVACY_VERSION,
        "phone": student.get("phone"),
        "email": student.get("email"),
        "guardian_phone": (student.get("guardian") or {}).get("phone"),
        "under_18": age is not None and age < 18,
        "guardian_consent": bool((student.get("guardian_consent") or {}).get("recorded")),
        "done": bool(ctx.user.get("onboarded_at")),
    }


def complete(
    ctx: AuthContext,
    *,
    phone: str,
    email: str | None,
    privacy_version: str,
    language: str,
    ip: str,
    user_agent: str,
) -> dict[str, Any]:
    if privacy_version != PRIVACY_VERSION:
        raise AppError(409, "The privacy notice has changed. Please read the new one.", "notice_changed")
    student = students.my_student(ctx)
    contact = {"phone": phone, "email": email.lower() if email else None}
    db = get_db()
    now = datetime.now(UTC)

    def work(session) -> None:
        students.apply_changes(
            ctx, student, contact, action="students.contact_confirmed", ip=ip, reason=None, session=session
        )
        db.consents.insert_one(
            {
                "user_id": ctx.user_id,
                "student_id": student["_id"],
                "notice": "privacy",
                "version": privacy_version,
                "language": language,
                "accepted_at": now,
                "ip": ip,
                "user_agent": user_agent,
            },
            session=session,
        )
        db.users.update_one(
            {"_id": ctx.user_id}, {"$set": {"onboarded_at": now, "language": language}}, session=session
        )
        audit.record(
            "students.privacy_accepted",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            details={"version": privacy_version, "language": language},
            session=session,
        )

    run_in_transaction(work)
    ctx.user.update(onboarded_at=now, language=language)
    return status(ctx)


def set_language(ctx: AuthContext, language: str) -> None:
    get_db().users.update_one({"_id": ctx.user_id}, {"$set": {"language": language}})
