"""
Notices (spec §3.10, plan item 1.13): text and/or a PDF, an audience, a publish time, an expiry
and a pin; optional Hindi/Marathi versions typed by staff; email to the audience.

Who sees a notice is decided in one place, `_visible_query`: students see notices for everyone,
for all students, or for their own class (programme, optionally year and division); staff see
notices for everyone and for staff; publishers see every notice to manage it.
"""

import re
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, files
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.email import send_email
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.notices.schemas import NoticeIn, NoticeUpdate
from app.modules.setup import service as setup
from app.modules.students import service as students

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
    return view(_get(notice_id))


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
    if ctx.user.get("kind") == "student":
        s = get_db().students.find_one({"user_id": ctx.user_id})
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
