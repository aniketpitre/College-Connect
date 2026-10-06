"""
Notices (spec §3.10, plan items 1.13 and 5.2): text and/or a PDF, an audience, a publish time, an
expiry and a pin; Hindi/Marathi versions typed by staff or translated automatically (marked
`machine` until staff save their own); email to the audience. Every change re-indexes the notice
into the help desk (`knowledge.index_notice`), for its own audience only, or the public help desk
too when marked `public`.

Who sees a notice is decided in one place, `_visible_query`: students see notices for everyone,
for all students, or for their own class (programme, optionally year and division); staff see
notices for everyone and for staff; publishers see every notice to manage it.
"""

import logging
import re
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import anthropic
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, files, ratelimit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.knowledge import service as knowledge
from app.modules.notices.schemas import NoticeIn, NoticeUpdate
from app.modules.setup import service as setup
from app.modules.students import service as students
from app.rag import generator

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
EMAIL_CHUNK = 100

register_indexes(
    "notices",
    [
        IndexModel([("status", ASCENDING), ("publish_at", DESCENDING)]),
        IndexModel([("audience.kind", ASCENDING), ("audience.programme_id", ASCENDING)]),
    ],
)
register_indexes("notice_emails", [IndexModel([("notice_id", ASCENDING), ("user_id", ASCENDING)], unique=True)])


def oid(value: Any, what: str = "Notice") -> ObjectId:
    return students.oid(value, what)


def _audience_doc(a: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {"kind": a.kind}
    if a.kind == "class":
        programme = get_db().programmes.find_one({"_id": oid(a.programme_id, "Programme")})
        if not programme:
            raise AppError(422, "Programme not found.", field="programme_id")
        doc["programme_id"] = programme["_id"]
        if a.year_of_study:
            if a.year_of_study > programme["duration_years"]:
                raise AppError(
                    422, f"{programme['code']} has {programme['duration_years']} years.", field="year_of_study"
                )
            doc["year_of_study"] = a.year_of_study
        if a.division_id:
            division = get_db().divisions.find_one({"_id": oid(a.division_id, "Division")})
            if (
                not division
                or division["programme_id"] != programme["_id"]
                or division["year_of_study"] != a.year_of_study
            ):
                raise AppError(422, "That division is not part of this class.", field="division_id")
            doc["division_id"] = division["_id"]
    return doc


def _expires_at(d: date | None) -> datetime | None:
    """A notice expires at the end of its expiry day, India time."""
    return datetime.combine(d, time.max, tzinfo=IST).astimezone(UTC) if d else None


def _translations(body: NoticeIn | NoticeUpdate) -> dict[str, Any]:
    out = {}
    for lang in ("hi", "mr"):
        t = getattr(body, lang)
        if t is not None:
            out[lang] = (
                {"title": t.title.strip(), "body": t.body.strip()} if (t.title.strip() or t.body.strip()) else None
            )
    return out


def audience_label(a: dict[str, Any]) -> str:
    if a["kind"] != "class":
        return {"everyone": "Everyone", "students": "All students", "staff": "Staff"}[a["kind"]]
    lookups = students._lookups()
    p = lookups["programmes"].get(a.get("programme_id"), {})
    parts = [p.get("code", "?")]
    if a.get("year_of_study"):
        labels = p.get("year_labels", [])
        parts.append(labels[a["year_of_study"] - 1] if len(labels) >= a["year_of_study"] else str(a["year_of_study"]))
    if a.get("division_id"):
        parts.append(lookups["divisions"].get(a["division_id"], {}).get("name", "?"))
    return " ".join(parts)


def view(n: dict[str, Any], *, full: bool = True) -> dict[str, Any]:
    now = datetime.now(UTC)
    a = n["audience"]
    state = n["status"]
    if state == "published" and n["publish_at"] > now:
        state = "scheduled"
    elif state == "published" and n.get("expires_at") and n["expires_at"] < now:
        state = "expired"
    result = {
        "id": str(n["_id"]),
        "title": n["title"],
        "hi": n.get("hi"),
        "mr": n.get("mr"),
        "audience": {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in a.items()},
        "audience_label": audience_label(a),
        "publish_at": n["publish_at"].isoformat(),
        "expires_on": n["expires_on"] if n.get("expires_on") else None,
        "pinned": n.get("pinned", False),
        "public": n.get("public", False),
        "state": state,
        "has_attachment": bool(n.get("attachment_file_id")),
        "author": n.get("author_name"),
        "emailed": n.get("emailed", 0),
    }
    if full:
        result["body"] = n["body"]
    return result


def create(ctx: AuthContext, body: NoticeIn, ip: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    publish_at = body.publish_at.astimezone(UTC) if body.publish_at else now
    if body.expires_on and _expires_at(body.expires_on) < max(publish_at, now):  # type: ignore[operator]
        raise AppError(422, "The expiry date is before the notice would appear.", field="expires_on")
    doc: dict[str, Any] = {
        "title": body.title.strip(),
        "body": body.body.strip(),
        **_translations(body),
        "audience": _audience_doc(body.audience),
        "publish_at": publish_at,
        "expires_on": body.expires_on.isoformat() if body.expires_on else None,
        "expires_at": _expires_at(body.expires_on),
        "pinned": body.pinned,
        "public": body.public,
        "status": "published",
        "author_id": ctx.user_id,
        "author_name": ctx.user["name"],
        "created_at": now,
        "emailed": 0,
    }
    doc["_id"] = get_db().notices.insert_one(doc).inserted_id
    audit.record(
        "notices.published",
        actor_id=ctx.user_id,
        target_type="notice",
        target_id=doc["_id"],
        ip=ip,
        details={"title": doc["title"], "audience": audience_label(doc["audience"])},
    )
    knowledge.index_notice(doc["_id"])
    return view(doc)


def _get(notice_id: str) -> dict[str, Any]:
    n = get_db().notices.find_one({"_id": oid(notice_id)})
    if not n:
        raise AppError(404, "Notice not found.")
    return n


def update(ctx: AuthContext, notice_id: str, body: NoticeUpdate, ip: str) -> dict[str, Any]:
    n = _get(notice_id)
    changes: dict[str, Any] = {
        k: v
        for k, v in body.model_dump(exclude_unset=True, exclude={"hi", "mr", "reason", "expires_on"}).items()
        if v is not None
    }
    changes.update(_translations(body))
    if "expires_on" in body.model_fields_set:
        changes["expires_on"] = body.expires_on.isoformat() if body.expires_on else None
        changes["expires_at"] = _expires_at(body.expires_on)
    if body.status == "withdrawn" and not (body.reason and body.reason.strip()):
        raise AppError(422, "Say why the notice is withdrawn.", field="reason")
    if body.public and n["audience"]["kind"] not in ("everyone", "students"):
        raise AppError(422, "Only a notice for everyone or all students can be public.", field="public")
    if not changes:
        return view(n)
    changes["updated_at"] = datetime.now(UTC)
    changes["updated_by"] = ctx.user_id
    get_db().notices.update_one({"_id": n["_id"]}, {"$set": changes})
    audit.record(
        "notices.withdrawn" if body.status == "withdrawn" else "notices.updated",
        actor_id=ctx.user_id,
        target_type="notice",
        target_id=n["_id"],
        ip=ip,
        reason=body.reason,
        details={"fields": sorted(k for k in changes if k not in {"updated_at", "updated_by"})},
    )
    knowledge.index_notice(n["_id"])
    return view(_get(notice_id))


def attach(ctx: AuthContext, notice_id: str, filename: str, data: bytes, ip: str) -> dict[str, Any]:
    n = _get(notice_id)
    saved = files.save(data, filename=filename, student_id=None, purpose="notice", created_by=ctx.user_id)
    if saved["content_type"] != "application/pdf":
        get_db().files.delete_one({"_id": saved["_id"]})
        raise AppError(415, "Attach a PDF.", "unsupported_file", "file")
    get_db().notices.update_one(
        {"_id": n["_id"]}, {"$set": {"attachment_file_id": saved["_id"], "attachment_name": saved["filename"]}}
    )
    audit.record("notices.attachment_added", actor_id=ctx.user_id, target_type="notice", target_id=n["_id"], ip=ip)
    knowledge.index_notice(n["_id"])
    return view(_get(notice_id))


# --- automatic translation (plan 5.2) -------------------------------------------------------


def translate(title: str, body: str) -> dict[str, dict[str, str]]:
    """Hindi and Marathi drafts of a notice, for staff to check before publishing."""
    if not generator.llm_available():
        raise AppError(503, "Automatic translation isn't set up on this server.", "not_configured")
    if len(body) > generator.TRANSLATE_MAX_CHARS:
        raise AppError(
            422,
            f"Notices up to {generator.TRANSLATE_MAX_CHARS:,} characters are translated automatically; "
            "translate a shorter summary.",
            field="body",
        )
    try:
        t = generator.translate_notice(title.strip(), body.strip())
    except anthropic.APIError as e:
        log.warning("Notice translation failed: %s", type(e).__name__)
        raise AppError(502, "The translation service didn't answer. Try again in a minute.", "unavailable") from e
    if t is None:
        raise AppError(422, "This notice could not be translated automatically.", "not_translated")
    return {
        "hi": {"title": t.hi_title.strip(), "body": t.hi_body.strip()},
        "mr": {"title": t.mr_title.strip(), "body": t.mr_body.strip()},
    }


def translate_for(ctx: AuthContext, title: str, body: str) -> dict[str, dict[str, str]]:
    ratelimit.hit(f"translate:{ctx.user_id}", 30, 3600, "Too many translations this hour. Try again later.")
    return translate(title, body)


def needs_translation(n: dict[str, Any]) -> bool:
    return (
        n["status"] == "published"
        and not (n.get("hi") and n.get("mr"))
        and len(n.get("body", "")) <= generator.TRANSLATE_MAX_CHARS
        and generator.llm_available()
    )


def auto_translate(notice_id: ObjectId) -> bool:
    """Fills in the missing Hindi/Marathi versions of a published notice (marked `machine`), then
    re-indexes it. Runs after the response (and daily for any that failed); never raises."""
    db = get_db()
    n = db.notices.find_one({"_id": notice_id})
    if not n or not needs_translation(n):
        return False
    try:
        t = translate(n["title"], n.get("body", ""))
    except AppError as e:
        log.warning("Automatic translation of notice %s failed: %s", notice_id, e.message)
        return False
    done = []
    for lang in ("hi", "mr"):
        # Only where staff haven't typed their own in the meantime.
        change = {lang: {**t[lang], "machine": True}, "updated_at": datetime.now(UTC)}
        r = db.notices.update_one({"_id": notice_id, lang: None}, {"$set": change})
        if r.modified_count:
            done.append(lang)
    if done:
        audit.record("notices.translated", target_type="notice", target_id=notice_id, details={"languages": done})
        knowledge.index_notice(notice_id)
    return bool(done)


def translate_pending(limit: int = 5) -> int:
    """Daily: translations that didn't happen at publishing (service down, key added later)."""
    if not generator.llm_available():
        return 0
    now = datetime.now(UTC)
    rows = (
        get_db()
        .notices.find(
            {
                "status": "published",
                "$or": [{"hi": None}, {"mr": None}],
                "$and": [{"$or": [{"expires_at": None}, {"expires_at": {"$gte": now}}]}],
            },
            {"_id": 1},
        )
        .limit(limit)
    )
    return sum(auto_translate(r["_id"]) for r in rows)


# --- who sees what --------------------------------------------------------------------------


def _visible_query(ctx: AuthContext, manage: bool = False) -> dict[str, Any]:
    if manage and P.NOTICES_PUBLISH in ctx.permissions:
        return {}
    now = datetime.now(UTC)
    live = {
        "status": "published",
        "publish_at": {"$lte": now},
        "$or": [{"expires_at": None}, {"expires_at": {"$gte": now}}],
    }
    if ctx.user.get("kind") in ("student", "parent"):
        from app.modules.students import service as students

        try:
            s: dict[str, Any] | None = students.my_student(ctx)  # parents see their child's notices
        except AppError:
            s = None
        mine: list[dict[str, Any]] = [{"audience.kind": {"$in": ["everyone", "students"]}}]
        if s and s.get("programme_id"):
            mine.append(
                {
                    "audience.kind": "class",
                    "audience.programme_id": s["programme_id"],
                    "audience.year_of_study": {"$in": [None, s.get("year_of_study")]},
                    "audience.division_id": {"$in": [None, s.get("division_id")]},
                }
            )
        return {"$and": [live, {"$or": mine}]}
    if P.NOTICES_READ in ctx.permissions:
        return {"$and": [live, {"audience.kind": {"$in": ["everyone", "staff"]}}]}
    raise AppError(403, "You can't see notices.", "forbidden")


def list_notices(ctx: AuthContext, *, manage: bool, q: str | None, limit: int = 200) -> list[dict[str, Any]]:
    query = _visible_query(ctx, manage)
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query = {"$and": [query, {"$or": [{"title": rx}, {"body": rx}, {"hi.title": rx}, {"mr.title": rx}]}]}
    rows = get_db().notices.find(query).sort([("pinned", DESCENDING), ("publish_at", DESCENDING)]).limit(limit)
    return [view(n, full=False) for n in rows]


def get_visible(ctx: AuthContext, notice_id: str) -> dict[str, Any]:
    n = get_db().notices.find_one({"$and": [{"_id": oid(notice_id)}, _visible_query(ctx, manage=True)]})
    if not n:
        raise AppError(404, "Notice not found.")
    return n


def recent_for_student(ctx: AuthContext, days: int = 7, limit: int = 3) -> list[dict[str, Any]]:
    since = datetime.now(UTC).timestamp() - days * 86400
    rows = (
        get_db().notices.find(_visible_query(ctx)).sort([("pinned", DESCENDING), ("publish_at", DESCENDING)]).limit(20)
    )
    return [view(n, full=False) for n in rows if n["publish_at"].timestamp() >= since or n.get("pinned")][:limit]


# --- email ----------------------------------------------------------------------------------


def _recipients(n: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    a = n["audience"]
    people: list[dict[str, Any]] = []
    if a["kind"] in {"everyone", "staff"}:
        people += list(
            db.users.find({"kind": "staff", "status": "active", "email": {"$type": "string"}}, {"email": 1, "name": 1})
        )
    if a["kind"] in {"everyone", "students", "class"}:
        sq: dict[str, Any] = {"status": "active", "email": {"$type": "string"}}
        if a["kind"] == "class":
            sq["programme_id"] = a["programme_id"]
            for key in ("year_of_study", "division_id"):
                if a.get(key):
                    sq[key] = a[key]
        people += [
            {"_id": s["user_id"], "email": s["email"], "name": s["name"]}
            for s in db.students.find(sq, {"user_id": 1, "email": 1, "name": 1})
        ]
    return people


def email_chunk(ctx: AuthContext, notice_id: str, base_url: str, ip: str) -> dict[str, Any]:
    """Emails the next EMAIL_CHUNK people in the audience who haven't had it; call until done."""
    n = _get(notice_id)
    if view(n)["state"] != "published":
        raise AppError(409, "Only a notice that is showing now can be emailed.", "conflict")
    db = get_db()
    people = _recipients(n)
    done = set(db.notice_emails.distinct("user_id", {"notice_id": n["_id"]}))
    todo = [p for p in people if p["_id"] not in done][:EMAIL_CHUNK]
    college = setup.institution().get("name") or "CollegeConnect"
    sent = failed = 0
    for p in todo:
        try:
            db.notice_emails.insert_one({"notice_id": n["_id"], "user_id": p["_id"], "at": datetime.now(UTC)})
        except DuplicateKeyError:
            continue  # another request is sending to this person
        ok = send_email(
            p["email"],
            f"{college}: {n['title']}",
            f"Dear {p['name']},\n\nA new notice from {college}:\n\n{n['title']}\n\n{n['body']}\n\n"
            f"Read it on CollegeConnect: {base_url.rstrip('/')}/app/notices/{n['_id']}\n",
        )
        if ok:
            sent += 1
        else:
            failed += 1
            db.notice_emails.delete_one({"notice_id": n["_id"], "user_id": p["_id"]})  # retry next time
    total_done = db.notice_emails.count_documents({"notice_id": n["_id"]})
    db.notices.update_one({"_id": n["_id"]}, {"$set": {"emailed": total_done}})
    if sent:
        audit.record(
            "notices.emailed",
            actor_id=ctx.user_id,
            target_type="notice",
            target_id=n["_id"],
            ip=ip,
            details={"sent": sent},
        )
    remaining = len(people) - total_done
    return {
        "sent": sent,
        "failed": failed,
        "emailed": total_done,
        "audience": len(people),
        "remaining": remaining,
        "done": remaining <= 0 or (not sent and failed > 0),
    }
