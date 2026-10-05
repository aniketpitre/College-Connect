"""
Read-only view of the audit log for the System Admin and the Principal (spec §3.19).

Newest first, 100 per page; `before` is the time of the last row of the previous page.
"""

import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.students.service import jsonable

PAGE = 100
IST = ZoneInfo("Asia/Kolkata")
AREAS = {
    "auth": "Sign-ins and passwords",
    "users": "Users and roles",
    "setup": "College setup",
    "students": "Student records",
    "fees": "Fees and receipts",
    "notices": "Notices",
    "exports": "Data exports",
    "onboarding": "First sign-in and consent",
}


def _day(value: str, field: str) -> datetime:
    try:
        return datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(), time.min, IST)
    except ValueError as e:
        raise AppError(422, "Use a date like 2026-10-04.", field=field) from e


def search(
    *,
    area: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    target_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    before: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {}
    if action:
        query["action"] = action
    elif area:
        if area not in AREAS:
            raise AppError(422, "Unknown area.", field="area")
        query["action"] = {"$regex": f"^{re.escape(area)}\\."}
    if actor:
        people = db.users.find(
            {"$or": [{"name": {"$regex": re.escape(actor), "$options": "i"}}, {"email": actor.strip().lower()}]},
            {"_id": 1},
        ).limit(50)
        query["actor_id"] = {"$in": [p["_id"] for p in people]}
    if target_id:
        try:
            query["target_id"] = {"$in": [ObjectId(target_id), target_id]}
        except InvalidId:
            query["target_id"] = target_id
    at: dict[str, Any] = {}
    if date_from:
        at["$gte"] = _day(date_from, "from")
    if date_to:
        at["$lt"] = _day(date_to, "to") + timedelta(days=1)
    if before:
        try:
            at["$lt"] = min(datetime.fromisoformat(before), at.get("$lt", datetime.fromisoformat(before)))
        except ValueError as e:
            raise AppError(422, "Bad page cursor.", field="before") from e
    if at:
        query["at"] = at

    rows = list(db.audit_log.find(query).sort("at", DESCENDING).limit(PAGE + 1))
    more = len(rows) > PAGE
    rows = rows[:PAGE]
    names = {
        u["_id"]: u["name"]
        for u in db.users.find({"_id": {"$in": list({r["actor_id"] for r in rows if r.get("actor_id")})}}, {"name": 1})
    }
    target_ids = [r["target_id"] for r in rows if isinstance(r.get("target_id"), ObjectId)]
    labels: dict[Any, str] = {}
    for s in db.students.find({"_id": {"$in": target_ids}}, {"name": 1, "prn": 1}):
        labels[s["_id"]] = f"{s['name']} ({s['prn']})"
    for u in db.users.find({"_id": {"$in": target_ids}}, {"name": 1}):
        labels.setdefault(u["_id"], u["name"])
    return {
        "rows": [
            {
                "id": str(r["_id"]),
                "at": r["at"].isoformat(),
                "action": r["action"],
                "actor": names.get(r.get("actor_id")),
                "actor_id": str(r["actor_id"]) if r.get("actor_id") else None,
                "target_type": r.get("target_type"),
                "target_id": str(r["target_id"]) if r.get("target_id") is not None else None,
                "target": labels.get(r.get("target_id")),
                "ip": r.get("ip"),
                "reason": r.get("reason"),
                "details": jsonable(r.get("details") or {}),
            }
            for r in rows
        ],
        "next_before": rows[-1]["at"].isoformat() if more else None,
        "areas": AREAS,
    }
