"""
Management dashboards (plan 4.3): the Principal's view of the whole college and the Accounts
view of money. Everything is counted from the records; attendance health comes from the daily
early-warning run (one small document per student), so the page stays fast.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

from app.core import clock
from app.core.db import get_db
from app.modules.attendance import stats
from app.modules.fees import ledger
from app.modules.setup import service as setup


def _year_entries(year_id: Any) -> dict[Any, list[dict[str, Any]]]:
    rows: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for e in (
        get_db()
        .ledger_entries.find(
            {"academic_year_id": year_id}, {"student_id": 1, "type": 1, "amount": 1, "installments": 1, "at": 1}
        )
        .sort("at", 1)
    ):
        rows[e["student_id"]].append(e)
    return rows


def principal() -> dict[str, Any]:
    db = get_db()
    year = setup.current_year()
    today = clock.today()
    out: dict[str, Any] = {"year": year["name"] if year else None}
    if year:
        cycles = list(db.admission_cycles.find({"academic_year_id": year["_id"]}, {"programmes": 1}))
        cycle_ids = [c["_id"] for c in cycles]
        out["admissions"] = {
            "seats": sum(p.get("seats", 0) for c in cycles for p in c.get("programmes", [])),
            "applied": db.applications.count_documents({"cycle_id": {"$in": cycle_ids}, "status": {"$ne": "draft"}}),
            "admitted": db.applications.count_documents({"cycle_id": {"$in": cycle_ids}, "status": "admitted"}),
        }
        totals: dict[str, int] = defaultdict(int)
        outstanding = 0
        for rows in _year_entries(year["_id"]).values():
            for e in rows:
                totals[e["type"]] += e["amount"]
            outstanding += max(sum(e["amount"] for e in rows), 0)
        due = totals["demand"] + totals["charge"] + totals["opening_due"]
        waived = -(totals["concession"] + totals["scholarship"])
        collected = -(totals["payment"] + totals["opening_paid"])
        out["fees"] = {
            "demand": due,
            "waived": waived,
            "collected": collected,
            "outstanding": outstanding,
            "percent": round(100 * collected / (due - waived), 1) if due - waived > 0 else None,
        }
        sheets: dict[str, int] = defaultdict(int)
        for r in db.marks_sheets.aggregate(
            [{"$match": {"academic_year_id": year["_id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        ):
            sheets[r["_id"]] = r["n"]
        total_sheets = sum(sheets.values())
        done = sheets.get("approved", 0) + sheets.get("locked", 0)
        out["marks"] = {
            "sheets": total_sheets,
            "done": done,
            "percent": round(100 * done / total_sheets, 1) if total_sheets else None,
        }
    minimum, _ = stats.thresholds()
    signals = [f["signals"].get("attendance") for f in db.risk_flags.find({}, {"signals": 1}) if f.get("signals")]
    known = [s for s in signals if s is not None]
    last = db.risk_flags.find_one({}, {"computed_at": 1}, sort=[("computed_at", -1)])
    out["attendance"] = {
        "average": round(sum(known) / len(known), 1) if known else None,
        "below_minimum": sum(1 for s in known if s < minimum),
        "minimum": minimum,
        "as_of": last.get("computed_at") if last else None,
    }
    since = datetime.combine(today - timedelta(days=90), time.min, tzinfo=clock.IST)
    issued = list(db.certificate_requests.find({"issued_at": {"$gte": since}}, {"requested_at": 1, "issued_at": 1}))
    days = [(r["issued_at"] - r["requested_at"]).total_seconds() / 86400 for r in issued if r.get("requested_at")]
    out["certificates"] = {
        "issued_90_days": len(issued),
        "average_days": round(sum(days) / len(days), 1) if days else None,
        "overdue": db.certificate_requests.count_documents(
            {"status": {"$in": ["requested", "verified", "signed"]}, "due_date": {"$lt": today.isoformat()}}
        ),
    }
    out["risk"] = {lv: db.risk_flags.count_documents({"level": lv}) for lv in ("high", "medium")}
    out["pending"] = {
        "approvals": db.approvals.count_documents({"status": "pending"}),
        "leave": db.leave_requests.count_documents({"status": "pending", "approver": "principal"}),
        "grievances_overdue": db.grievances.count_documents(
            {"sensitive": False, "status": {"$in": ["open", "in_progress"]}, "due_date": {"$lt": today.isoformat()}}
        ),
    }
    return out


def accounts() -> dict[str, Any]:
    db = get_db()
    today = clock.today()
    year = setup.current_year()

    def collected(since: datetime) -> dict[str, Any]:
        by_mode: dict[str, int] = defaultdict(int)
        for r in db.receipts.find({"status": "valid", "collected_at": {"$gte": since}}, {"amount": 1, "mode": 1}):
            by_mode[r["mode"]] += r["amount"]
        return {"total": sum(by_mode.values()), "by_mode": dict(by_mode)}

    start_of = lambda d: datetime.combine(d, time.min, tzinfo=clock.IST)  # noqa: E731
    out: dict[str, Any] = {
        "today": collected(start_of(today)),
        "month": collected(start_of(today.replace(day=1))),
    }
    if not year:
        return out
    out["year"] = collected(start_of(date.fromisoformat(year["start_date"])))
    years = {s["_id"]: s.get("year_of_study") for s in db.students.find({"status": "active"}, {"year_of_study": 1})}
    receivable = overdue = overdue_students = 0
    by_year: dict[int, int] = defaultdict(int)
    for sid, rows in _year_entries(year["_id"]).items():
        info = ledger.summary(rows, today)
        if info["balance"] > 0:
            receivable += info["balance"]
            by_year[years.get(sid) or 0] += info["balance"]
        if info["overdue"] > 0:
            overdue += info["overdue"]
            overdue_students += 1
    out["receivables"] = {
        "total": receivable,
        "overdue": overdue,
        "overdue_students": overdue_students,
        "by_year": [{"year_of_study": y, "amount": a} for y, a in sorted(by_year.items()) if y],
    }
    out["pending_approvals"] = db.approvals.count_documents({"status": "pending"})
    return out
