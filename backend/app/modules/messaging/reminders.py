"""
Fee reminders (spec R14 "Receives: fee-due reminders"), queued by the daily job.

- Three days before an installment is due, if something is still owed on it.
- One, seven and thirty days after it falls due, if it is still unpaid.

A reminder is queued once per student, installment and step (the `fee_reminders` index), so a
second run on the same day sends nothing new.
"""

from datetime import date
from typing import Any

from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import clock
from app.core.db import get_db, register_indexes
from app.core.money import format_inr
from app.modules.fees import ledger
from app.modules.messaging import service as messaging
from app.modules.setup import service as setup

register_indexes(
    "fee_reminders",
    [
        IndexModel([("student_id", ASCENDING), ("label", ASCENDING), ("step", ASCENDING)], unique=True),
        IndexModel([("at", ASCENDING)], expireAfterSeconds=400 * 24 * 3600),
    ],
)

BEFORE = 3
AFTER = (1, 7, 30)


def _once(student_id: Any, label: str, step: str) -> bool:
    try:
        get_db().fee_reminders.insert_one({"student_id": student_id, "label": label, "step": step, "at": clock.now()})
        return True
    except DuplicateKeyError:
        return False


def queue_fee_reminders(today: date | None = None) -> dict[str, int]:
    today = today or clock.today()
    year = setup.current_year()
    if not year:
        return {"due": 0, "overdue": 0}
    db = get_db()
    active = {s["_id"] for s in db.students.find({"status": "active"}, {"_id": 1})}
    by_student: dict[Any, list[dict[str, Any]]] = {}
    for e in db.ledger_entries.find({"academic_year_id": year["_id"]}).sort("at", ASCENDING):
        if e["student_id"] in active:
            by_student.setdefault(e["student_id"], []).append(e)
    due = overdue = 0
    for student_id, rows in by_student.items():
        info = ledger.summary(rows, today)
        for inst in info["installments"]:
            if inst["due"] <= 0:
                continue
            when = date.fromisoformat(inst["due_date"])
            days = (today - when).days
            if days == -BEFORE and _once(student_id, inst["label"], "before"):
                messaging.queue(
                    student_id,
                    "fee_due",
                    {"amount": format_inr(inst["due"], "₹"), "label": inst["label"], "date": when.strftime("%d %b")},
                )
                due += 1
            elif days in AFTER and _once(student_id, inst["label"], f"after{days}"):
                messaging.queue(student_id, "fee_overdue", {"amount": format_inr(info["overdue"], "₹")})
                overdue += 1
    return {"due": due, "overdue": overdue}
