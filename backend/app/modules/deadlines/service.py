"""
Deadline radar (plan 5.6, unique feature U3): dates found in notices become personal reminders.

1. When a notice is published or edited, its dates are found: by the AI when a key is set (with
   what to do, in English, Hindi and Marathi), otherwise by date patterns ("15 October",
   "15/10/2026", "2026-10-15") with the sentence around them. They are saved as *proposed*.
2. Staff confirm, correct or dismiss each one on the notice (nothing reaches students unchecked)
   and can add their own.
3. A confirmed deadline shows on the home page of every student (and parent) the notice is for,
   from 14 days before; the daily job sends a reminder 3 days before and on the day.

A withdrawn or expired notice takes its deadlines with it (they are listed through the notices the
person can see). Deadlines already past are kept for the record but never shown.
"""

import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.rag import generator

log = logging.getLogger(__name__)

register_indexes(
    "deadlines", [IndexModel([("notice_id", ASCENDING)]), IndexModel([("status", ASCENDING), ("date", ASCENDING)])]
)
register_indexes(
    "deadline_reminders",
    [
        IndexModel([("deadline_id", ASCENDING), ("student_id", ASCENDING), ("step", ASCENDING)], unique=True),
        IndexModel([("at", ASCENDING)], expireAfterSeconds=400 * 24 * 3600),
    ],
)

SHOW_DAYS = 14  # on the home page from this many days before
REMIND = {3: "before3", 0: "today"}
MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_PATTERNS = [
    # 15 October 2026, 15th Oct, 15 Oct, 2026
    re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<m>{_MONTH})\.?,?(?:\s+(?P<y>\d{{4}}))?\b", re.I),
    # October 15, 2026 / Oct 15th
    re.compile(rf"\b(?P<m>{_MONTH})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?(?:\s+(?P<y>\d{{4}}))?\b", re.I),
    # 15/10/2026, 15-10-26, 15.10.2026 (Indian order: day first)
    re.compile(r"\b(?P<d>\d{1,2})[/.-](?P<mn>\d{1,2})[/.-](?P<y>\d{4}|\d{2})\b"),
    # 2026-10-15
    re.compile(r"\b(?P<y>\d{4})-(?P<mn>\d{2})-(?P<d>\d{2})\b"),
]


def oid(value: Any, what: str = "Deadline") -> ObjectId:
    try:
        return ObjectId(str(value))
    except Exception as e:
        raise AppError(404, f"{what} not found.") from e


def _date(m: re.Match[str], today: date) -> date | None:
    g = m.groupdict()
    month = MONTHS[g["m"].lower()] if g.get("m") else int(g["mn"])
    day = int(g["d"])
    year = g.get("y")
    try:
        if year:
            y = int(year)
            return date(y + 2000 if y < 100 else y, month, day)
        found = date(today.year, month, day)
        return found if found >= today - timedelta(days=30) else date(today.year + 1, month, day)
    except ValueError:
        return None


def find_dates(title: str, body: str, today: date) -> list[dict[str, Any]]:
    """Deadline candidates by date patterns: the date and the sentence it is in (English only)."""
    out: dict[str, dict[str, Any]] = {}
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", f"{title}.\n{body}"):
        for pattern in _PATTERNS:
            for m in pattern.finditer(sentence):
                d = _date(m, today)
                if d is None or not (today <= d <= today + timedelta(days=365)):
                    continue
                what = re.sub(r"\s+", " ", sentence).strip(" .")[:160]
                out.setdefault(d.isoformat(), {"date": d.isoformat(), "what": {"en": what}})
    return sorted(out.values(), key=lambda x: x["date"])


def _ai_dates(title: str, body: str, today: date) -> list[dict[str, Any]] | None:
    if not generator.llm_available():
        return None
    try:
        found = generator.extract_deadlines(title, body[: generator.TRANSLATE_MAX_CHARS * 2], today.isoformat())
    except generator.LLM_ERRORS as e:
        log.warning("Deadline extraction failed (%s); using date patterns", type(e).__name__)
        return None
    out = []
    for d in found:
        try:
            when = date.fromisoformat(d.date)
        except ValueError:
            continue
        if today <= when <= today + timedelta(days=365):
            what = {"en": d.what_en.strip(), "hi": d.what_hi.strip(), "mr": d.what_mr.strip()}
            out.append({"date": when.isoformat(), "what": {k: v for k, v in what.items() if v}})
    return out


def propose(notice_id: ObjectId) -> int:
    """(Re)proposes a notice's deadlines; confirmed and dismissed ones are kept. Never raises."""
    db = get_db()
    n = db.notices.find_one({"_id": notice_id})
    if not n or n["status"] != "published":
        return 0
    today = clock.today()
    found = _ai_dates(n["title"], n.get("body", ""), today)
    source = "ai" if found is not None else "pattern"
    if found is None:
        found = find_dates(n["title"], n.get("body", ""), today)
    # Dates staff already decided on, including those they moved to another date.
    decided = db.deadlines.find({"notice_id": notice_id, "status": {"$in": ["confirmed", "dismissed"]}})
    kept = {x for d in decided for x in (d["date"], d.get("found"))}
    db.deadlines.delete_many({"notice_id": notice_id, "status": "proposed"})
    now = datetime.now(UTC)
    rows = [
        {
            "notice_id": notice_id,
            "date": f["date"],
            "found": f["date"],
            "what": f["what"],
            "status": "proposed",
            "source": source,
            "created_at": now,
        }
        for f in found
        if f["date"] not in kept
    ]
    if rows:
        db.deadlines.insert_many(rows)
    return len(rows)


def propose_later(notice_id: ObjectId) -> None:
    try:
        propose(notice_id)
    except Exception:  # noqa: BLE001 - a background step must not fail the request
        log.exception("Could not find deadlines in notice %s", notice_id)


# --- staff ------------------------------------------------------------------------------------


def _view(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(d["_id"]),
        "notice_id": str(d["notice_id"]),
        "date": d["date"],
        "what": d["what"],
        "status": d["status"],
        "source": d.get("source", "staff"),
    }


def for_notice(notice_id: str) -> list[dict[str, Any]]:
    rows = get_db().deadlines.find({"notice_id": oid(notice_id, "Notice")}).sort("date", ASCENDING)
    return [_view(d) for d in rows]


def _what(en: str, hi: str | None, mr: str | None) -> dict[str, str]:
    if len(en.strip()) < 3:
        raise AppError(422, "Say what students must do.", field="what")
    return {k: v.strip() for k, v in (("en", en), ("hi", hi or ""), ("mr", mr or "")) if v.strip()}


def add(ctx: AuthContext, notice_id: str, when: date, en: str, hi: str | None, mr: str | None, ip: str) -> dict:
    n = get_db().notices.find_one({"_id": oid(notice_id, "Notice")})
    if not n:
        raise AppError(404, "Notice not found.")
    if when < clock.today():
        raise AppError(422, "That date has passed.", field="date")
    doc = {
        "notice_id": n["_id"],
        "date": when.isoformat(),
        "what": _what(en, hi, mr),
        "status": "confirmed",
        "source": "staff",
        "created_at": datetime.now(UTC),
        "confirmed_by": ctx.user_id,
    }
    doc["_id"] = get_db().deadlines.insert_one(doc).inserted_id
    audit.record(
        "deadlines.added",
        actor_id=ctx.user_id,
        target_type="deadline",
        target_id=doc["_id"],
        ip=ip,
        details={"date": doc["date"]},
    )
    return _view(doc)


def decide(
    ctx: AuthContext,
    deadline_id: str,
    *,
    status: str,
    when: date | None,
    en: str | None,
    hi: str | None,
    mr: str | None,
    ip: str,
) -> dict[str, Any]:
    db = get_db()
    d = db.deadlines.find_one({"_id": oid(deadline_id)})
    if not d:
        raise AppError(404, "Deadline not found.")
    changes: dict[str, Any] = {"status": status, "decided_by": ctx.user_id, "decided_at": datetime.now(UTC)}
    if when is not None:
        if when < clock.today():
            raise AppError(422, "That date has passed.", field="date")
        changes["date"] = when.isoformat()
    if en is not None:
        changes["what"] = _what(en, hi, mr)
    db.deadlines.update_one({"_id": d["_id"]}, {"$set": changes})
    audit.record(
        f"deadlines.{status}",
        actor_id=ctx.user_id,
        target_type="deadline",
        target_id=d["_id"],
        ip=ip,
        details={"date": changes.get("date", d["date"])},
    )
    return _view({**d, **changes})


# --- students and parents ---------------------------------------------------------------------


def upcoming(ctx: AuthContext, days: int = SHOW_DAYS) -> list[dict[str, Any]]:
    """Confirmed deadlines of the notices this student (or parent's child) can see, soonest first."""
    from app.modules.notices import service as notices

    db = get_db()
    today = clock.today()
    visible = [n["_id"] for n in db.notices.find(notices._visible_query(ctx), {"_id": 1})]
    rows = db.deadlines.find(
        {
            "notice_id": {"$in": visible},
            "status": "confirmed",
            "date": {"$gte": today.isoformat(), "$lte": (today + timedelta(days=days)).isoformat()},
        }
    ).sort("date", ASCENDING)
    return [{**_view(d), "days_left": (date.fromisoformat(d["date"]) - today).days} for d in rows.limit(10)]


# --- reminders (daily job) --------------------------------------------------------------------


def _students_for(audience: dict[str, Any]) -> list[ObjectId]:
    if audience["kind"] == "staff":
        return []
    q: dict[str, Any] = {"status": "active"}
    if audience["kind"] == "class":
        q["programme_id"] = audience["programme_id"]
        for key in ("year_of_study", "division_id"):
            if audience.get(key):
                q[key] = audience[key]
    return [s["_id"] for s in get_db().students.find(q, {"_id": 1})]


def daily(today: date | None = None) -> dict[str, int]:
    """Queues a reminder 3 days before each confirmed deadline and on the day, once per student."""
    from app.modules.messaging import service as messaging

    today = today or clock.today()
    db = get_db()
    queued = 0
    for days_before, step in REMIND.items():
        on = (today + timedelta(days=days_before)).isoformat()
        for d in db.deadlines.find({"status": "confirmed", "date": on}):
            n = db.notices.find_one({"_id": d["notice_id"], "status": "published"})
            if not n or (n.get("expires_at") and n["expires_at"] < datetime.now(UTC)):
                continue
            for sid in _students_for(n["audience"]):
                try:
                    db.deadline_reminders.insert_one(
                        {"deadline_id": d["_id"], "student_id": sid, "step": step, "at": clock.now()}
                    )
                except DuplicateKeyError:
                    continue
                messaging.queue(
                    sid,
                    "deadline_soon",
                    {"what": d["what"]["en"], "date": date.fromisoformat(d["date"]).strftime("%d %b")},
                )
                queued += 1
    return {"reminders": queued}
