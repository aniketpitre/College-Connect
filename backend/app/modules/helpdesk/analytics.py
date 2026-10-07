"""Help-desk query logging and the aggregates behind the admin analytics page."""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError

from app.core.db import db_available, get_db, register_indexes

log = logging.getLogger(__name__)

register_indexes(
    "queries",
    [IndexModel([("created_at", ASCENDING)]), IndexModel([("grounded", ASCENDING), ("created_at", DESCENDING)])],
)


def _queries():
    return get_db()["queries"]


def log_query(
    question: str,
    language: str,
    category_filter: str | None,
    result: dict,
    latency_ms: int,
    channel: str = "public",
) -> None:
    """Best effort: a logging failure must never affect the student's answer."""
    if not db_available() or result.get("chat"):
        return  # greetings and unrelated questions are not questions the documents should answer
    try:
        _queries().insert_one(
            {
                "created_at": datetime.now(UTC),
                "question": question,
                "language": language,
                "category_filter": category_filter,
                # Unanswered questions have no real office; don't count them under the default one.
                "category": result["category"] if result["grounded"] else category_filter,
                "grounded": result["grounded"],
                "confidence": result["confidence"],
                "sources": [f"{s['document']} · {s['section']}" for s in result["sources"]],
                "latency_ms": latency_ms,
                "channel": channel,  # public help desk or the signed-in portal; never who asked
                "qkey": question_key(question),
            }
        )
    except PyMongoError:
        log.exception("Could not log query to MongoDB")


def _count_by(coll, match: dict, field: str) -> dict[str, int]:
    rows = coll.aggregate([{"$match": match}, {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}])
    return {str(r["_id"]): r["n"] for r in rows if r["_id"] is not None}


def admin_stats(days: int = 7) -> dict:
    coll = _queries()
    since = datetime.now(UTC) - timedelta(days=days)
    match = {"created_at": {"$gte": since}}

    total = coll.count_documents(match)
    grounded = coll.count_documents({**match, "grounded": True})
    latency = list(
        coll.aggregate(
            [
                {"$match": match},
                {"$group": {"_id": None, "avg_latency": {"$avg": "$latency_ms"}, "avg_conf": {"$avg": "$confidence"}}},
            ]
        )
    )

    def _rows(query: dict, limit: int) -> list[dict]:
        cursor = coll.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [{**r, "created_at": r["created_at"].isoformat()} for r in cursor]

    return {
        "days": days,
        "total_queries": total,
        "all_time_queries": coll.estimated_document_count(),
        "grounded_rate": round(grounded / total, 3) if total else None,
        "avg_latency_ms": round(latency[0]["avg_latency"]) if latency else None,
        "avg_confidence": round(latency[0]["avg_conf"], 2) if latency else None,
        "by_category": _count_by(coll, match, "category"),
        "by_language": _count_by(coll, match, "language"),
        # Questions the documents couldn't answer: what the college should publish next.
        "knowledge_gaps": _rows({**match, "grounded": False}, 15),
        "recent": _rows(match, 25),
    }


# --- knowledge gaps (plan 5.7): what the help desk couldn't answer, for the office to publish -----


def question_key(question: str) -> str:
    """The same question asked with different case, spacing or punctuation groups together."""
    return " ".join(re.findall(r"[\w\u0900-\u097F]+", question.lower()))


def gaps(days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Unanswered questions not yet dealt with, grouped, most asked first."""
    since = datetime.now(UTC) - timedelta(days=days)
    groups: dict[str, dict[str, Any]] = {}
    rows = (
        _queries()
        .find(
            {"created_at": {"$gte": since}, "grounded": False, "gap_closed": {"$ne": True}},
            {"question": 1, "language": 1, "created_at": 1, "channel": 1},
        )
        .sort("created_at", -1)
        .limit(5000)
    )
    for r in rows:
        key = question_key(r["question"])
        if not key:
            continue
        g = groups.setdefault(
            key, {"key": key, "question": r["question"], "count": 0, "languages": set(), "last_at": r["created_at"]}
        )
        g["count"] += 1
        g["languages"].add(r.get("language", "en"))
    ranked = sorted(groups.values(), key=lambda g: (-g["count"], -g["last_at"].timestamp()))[:limit]
    return [{**g, "languages": sorted(g["languages"]), "last_at": g["last_at"].isoformat()} for g in ranked]


def close_gap(key: str, how: str, doc_id: Any = None) -> int:
    """Marks every unanswered asking of this question as dealt with (answered as an FAQ, or dismissed)."""
    done = {"gap_closed": True, "gap_closed_how": how, "gap_doc_id": doc_id, "gap_closed_at": datetime.now(UTC)}
    open_gaps = {"grounded": False, "gap_closed": {"$ne": True}}
    closed = _queries().update_many({**open_gaps, "qkey": key}, {"$set": done}).modified_count
    # Questions logged before the key was stored.
    for q in _queries().find({**open_gaps, "qkey": {"$exists": False}}, {"question": 1}):
        if question_key(q["question"]) == key:
            _queries().update_one({"_id": q["_id"]}, {"$set": done})
            closed += 1
    return closed
