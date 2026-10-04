"""Query logging and the aggregates behind the admin dashboard."""

import logging
from datetime import UTC, datetime, timedelta

from pymongo.errors import PyMongoError

from app.db import db_available, get_db

log = logging.getLogger(__name__)

_indexes_ready = False


def _queries():
    global _indexes_ready
    coll = get_db()["queries"]
    if not _indexes_ready:
        coll.create_index("created_at")
        coll.create_index([("grounded", 1), ("created_at", -1)])
        _indexes_ready = True
    return coll


def log_query(
    question: str,
    language: str,
    category_filter: str | None,
    result: dict,
    latency_ms: int,
) -> None:
    """Best effort: a logging failure must never affect the student's answer."""
    if not db_available():
        return
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
