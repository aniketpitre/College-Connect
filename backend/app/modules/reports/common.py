"""Shared pieces for the accreditation and government reports: the year, people counts, CSV."""

import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Any

from bson import ObjectId

from app.core import clock
from app.core.db import get_db
from app.core.errors import AppError
from app.modules.setup import service as setup
from app.modules.students import service as students

TEACHING = {"faculty", "hod", "mentor", "principal"}
# AISHE groups the Maharashtra categories into five social groups.
AISHE_GROUP = {"OPEN": "general", "EWS": "ews", "SC": "sc", "ST": "st"}  # everything else counts as OBC
GROUP_LABELS = {"general": "General", "ews": "EWS", "sc": "SC", "st": "ST", "obc": "OBC"}


def year(year_id: str | None) -> dict[str, Any]:
    if year_id:
        doc = get_db().academic_years.find_one({"_id": students.oid(year_id, "Academic year")})
        if not doc:
            raise AppError(404, "Academic year not found.", field="year_id")
        return doc
    doc = setup.current_year()
    if not doc:
        raise AppError(409, "Set the current academic year in College setup first.", "no_current_year")
    return doc


def span(y: dict[str, Any]) -> tuple[datetime, datetime]:
    """The year as a time range (India time), for records stamped with a time."""
    first = datetime.combine(date.fromisoformat(y["start_date"]), time.min, tzinfo=clock.IST)
    last = datetime.combine(date.fromisoformat(y["end_date"]) + timedelta(days=1), time.min, tzinfo=clock.IST)
    return first, last


def is_current(y: dict[str, Any]) -> bool:
    return bool(y.get("is_current"))


def programmes() -> dict[ObjectId, dict[str, Any]]:
    return {p["_id"]: p for p in get_db().programmes.find({"status": {"$ne": "archived"}})}


def category_groups() -> dict[ObjectId, str]:
    return {c["_id"]: AISHE_GROUP.get(c["code"], "obc") for c in get_db().categories.find({}, {"code": 1})}


def active_students(fields: dict[str, int] | None = None) -> list[dict[str, Any]]:
    return list(get_db().students.find({"status": "active"}, fields or None))


def teachers() -> tuple[list[dict[str, Any]], int]:
    """Teaching staff records (user + profile) still with the college, and how many teaching
    accounts have no staff record yet."""
    db = get_db()
    users = list(db.users.find({"kind": "staff", "status": {"$ne": "disabled"}}, {"name": 1, "roles": 1}))
    profiles = {p["_id"]: p for p in db.staff_profiles.find({"_id": {"$in": [u["_id"] for u in users]}})}
    out, missing = [], 0
    for u in users:
        p = profiles.get(u["_id"])
        if p is None:
            missing += int(bool(set(u.get("roles", [])) & TEACHING))
            continue
        if p.get("teaching") and not p.get("left_on"):
            out.append({**p, "name": u["name"]})
    return out, missing


def to_csv(columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow(["" if r.get(k) is None else r.get(k) for k, _ in columns])
    return buf.getvalue()


def pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None
