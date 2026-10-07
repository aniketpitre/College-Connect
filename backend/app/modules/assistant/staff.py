"""
Staff assistant (plan 5.8): "How many SY BCA students owe more than ₹10,000?" answered by
running one of a few **pre-defined, permission-checked queries** and showing the numbers and the
list behind them. The AI (or, without a key, a keyword parser) only picks the query and its
filters; it never sees or queries the database, and each query checks the asker's permissions
the same way the matching ERP page does.

Queries:
- `fees_outstanding`: students whose balance (or overdue amount) is above an amount. FEES_READ.
- `attendance_below`: students below an attendance percentage (default: the college minimum),
  in the classes the person may read (all, their department, or the classes they teach).
- `certificates_pending`: open certificate requests (optionally past the promised date, or of
  one type). CERT_MANAGE or CERT_READ.
- `backlogs`: students with subjects still to clear. RESULTS_READ or MARKS_READ.
Filters: programme, year of study, division. Every question run is recorded in the audit log.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError
from app.core.money import format_inr
from app.core.rbac import P
from app.rag import generator

log = logging.getLogger(__name__)

MAX_ROWS = 200
TOOLS = ("fees_outstanding", "attendance_below", "certificates_pending", "backlogs")
EXAMPLES = [
    "How many SY BCA students owe more than ₹10,000?",
    "Which FY students have overdue fees?",
    "Who is below 75% attendance in BCA FY A?",
    "Which certificate requests are past the promised date?",
    "Which TY students have backlogs?",
]
CERT_TYPES = {
    "bonafide": "bonafide",
    "character": "character",
    "fee paid": "fee_paid",
    "fee-paid": "fee_paid",
    "tc": "tc",
    "transfer": "tc",
    "migration": "migration",
    "noc": "noc",
}
YEAR_WORDS = {
    "fy": 1,
    "first": 1,
    "1st": 1,
    "sy": 2,
    "second": 2,
    "2nd": 2,
    "ty": 3,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
}


@dataclass
class Plan:
    tool: str | None
    programme: str | None = None  # programme code, e.g. BCA
    year: int | None = None
    division: str | None = None  # division name, e.g. A
    min_amount: int | None = None  # paise
    overdue_only: bool = False
    below: float | None = None  # attendance percent
    cert_type: str | None = None
    notes: list[str] = field(default_factory=list)


# --- understanding the question ---------------------------------------------------------------


def _amount(text: str) -> int | None:
    m = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh|lakhs)?", text, re.I) or re.search(
        r"\b([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|rupees)\b", text, re.I
    )
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    value *= {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000}.get(unit, 1)
    return round(value * 100)


def parse(question: str) -> Plan:
    """The keyword parser: used without an AI key, and to check the AI's choice of filters."""
    q = question.lower()
    words = set(re.findall(r"[a-z0-9]+", q))
    if words & {"owe", "owes", "dues", "due", "fee", "fees", "balance", "outstanding", "unpaid", "pending"} and not (
        words & {"certificate", "certificates", "bonafide", "tc"}
    ):
        tool = "fees_outstanding"
    elif words & {"attendance", "absent", "defaulter", "defaulters"}:
        tool = "attendance_below"
    elif words & {"certificate", "certificates", "bonafide", "tc", "migration", "noc"}:
        tool = "certificates_pending"
    elif words & {"backlog", "backlogs", "kt", "atkt", "clear", "failed"}:
        tool = "backlogs"
    else:
        tool = None
    plan = Plan(tool=tool)
    codes = {p["code"].lower(): p["code"] for p in get_db().programmes.find({}, {"code": 1})}
    plan.programme = next((codes[w] for w in words if w in codes), None)
    plan.year = next((YEAR_WORDS[w] for w in re.findall(r"[a-z0-9]+", q) if w in YEAR_WORDS), None)
    if m := re.search(r"\byear\s*([1-6])\b", q):
        plan.year = int(m.group(1))
    if m := re.search(r"\b(?:div(?:ision)?\.?\s*([a-z])|(?:fy|sy|ty)\s+(?:[a-z]+\s+)?([a-z])\b(?!\w))", q):
        name = (m.group(1) or m.group(2) or "").upper()
        if name and name not in {"S", "I"}:  # "SY BCA students", "in"
            plan.division = name
    if tool == "fees_outstanding":
        plan.min_amount = _amount(question)
        plan.overdue_only = bool(words & {"overdue", "late", "defaulter", "defaulters"})
    if tool == "attendance_below" and (m := re.search(r"(\d{1,3})\s*%", q)):
        plan.below = float(m.group(1))
    if tool == "certificates_pending":
        plan.cert_type = next((v for k, v in CERT_TYPES.items() if k in q), None)
        plan.overdue_only = bool(words & {"overdue", "late", "past", "delayed"})
    return plan


def _ai_plan(question: str) -> Plan | None:
    if not generator.llm_available():
        return None
    try:
        p = generator.plan_staff_query(question)
    except anthropic.APIError as e:
        log.warning("Staff query planning failed (%s); using keywords", type(e).__name__)
        return None
    if p is None or p.tool not in TOOLS:
        return Plan(tool=None) if p is not None else None
    return Plan(
        tool=p.tool,
        programme=(p.programme or None),
        year=p.year,
        division=(p.division or None),
        min_amount=round(p.min_amount_rupees * 100) if p.min_amount_rupees else None,
        overdue_only=bool(p.overdue_only),
        below=p.below_percent,
        cert_type=p.certificate_type if p.certificate_type in CERT_TYPES.values() else None,
    )


# --- the queries ------------------------------------------------------------------------------


def _student_filter(plan: Plan) -> tuple[dict[str, Any], list[str]]:
    db = get_db()
    f: dict[str, Any] = {"status": "active"}
    labels: list[str] = []
    programme = None
    if plan.programme:
        programme = db.programmes.find_one({"code": {"$regex": f"^{re.escape(plan.programme)}$", "$options": "i"}})
        if not programme:
            raise AppError(422, f"There is no programme {plan.programme}.")
        f["programme_id"] = programme["_id"]
        labels.append(programme["code"])
    if plan.year:
        f["year_of_study"] = plan.year
        year_labels = (programme or {}).get("year_labels") or []
        labels.append(year_labels[plan.year - 1] if len(year_labels) >= plan.year else f"year {plan.year}")
    if plan.division:
        q: dict[str, Any] = {"name": {"$regex": f"^{re.escape(plan.division)}$", "$options": "i"}}
        for key in ("programme_id", "year_of_study"):
            if key in f:
                q[key] = f[key]
        ids = [d["_id"] for d in db.divisions.find(q, {"_id": 1})]
        if ids:
            f["division_id"] = {"$in": ids}
            labels.append(f"division {plan.division.upper()}")
    return f, labels


def _need(ctx: AuthContext, *perms: P) -> None:
    if not ctx.permissions & set(perms):
        raise AppError(403, "You don't have access to that information.", "forbidden")


def _class(s: dict[str, Any], lookups: dict[str, Any]) -> str:
    from app.modules.students import service as students

    sm = students.summary(s, lookups)
    return " ".join(x for x in (sm["programme_code"], sm["year_label"], sm["division"]) if x)


def _fees(ctx: AuthContext, plan: Plan) -> dict[str, Any]:
    from app.modules.fees import ledger
    from app.modules.setup import service as setup
    from app.modules.students import service as students

    _need(ctx, P.FEES_READ)
    year = setup.current_year()
    if not year:
        raise AppError(409, "No current academic year is set.")
    sf, labels = _student_filter(plan)
    db = get_db()
    roster = {s["_id"]: s for s in db.students.find(sf)}
    entries: dict[Any, list[dict[str, Any]]] = {}
    for e in db.ledger_entries.find({"academic_year_id": year["_id"], "student_id": {"$in": list(roster)}}).sort(
        "at", 1
    ):
        entries.setdefault(e["student_id"], []).append(e)
    lookups = students._lookups()
    today = clock.today()
    rows = []
    for sid, es in entries.items():
        acc = ledger.summary(es, today)
        amount = acc["overdue"] if plan.overdue_only else acc["balance"]
        if amount <= 0 or (plan.min_amount is not None and amount <= plan.min_amount):
            continue
        s = roster[sid]
        rows.append(
            {
                "prn": s["prn"],
                "student": s["name"],
                "class": _class(s, lookups),
                "balance": acc["balance"],
                "overdue": acc["overdue"],
                "student_id": str(sid),
            }
        )
    rows.sort(key=lambda r: -r["overdue" if plan.overdue_only else "balance"])
    what = "overdue fees" if plan.overdue_only else "fees outstanding"
    if plan.min_amount is not None:
        what += f" above {format_inr(plan.min_amount, '₹')}"
    total = sum(r["overdue" if plan.overdue_only else "balance"] for r in rows)
    return {
        "summary": f"{len(rows)} {' '.join(labels) + ' ' if labels else ''}students have {what} for {year['name']}; "
        f"together {format_inr(total, '₹')}.",
        "count": len(rows),
        "total": total,
        "columns": [
            ("prn", "PRN", "text"),
            ("student", "Student", "text"),
            ("class", "Class", "text"),
            ("balance", "Balance", "money"),
            ("overdue", "Overdue", "money"),
        ],
        "rows": rows,
        "link": "/app/fees/reports",
    }


def _attendance(ctx: AuthContext, plan: Plan) -> dict[str, Any]:
    from app.modules.attendance import service as attendance
    from app.modules.attendance import stats

    if not ctx.permissions & {P.ATTENDANCE_READ, P.ATTENDANCE_READ_DEPT, P.ATTENDANCE_TAKE}:
        raise AppError(403, "You don't have access to that information.", "forbidden")
    minimum, _ = stats.thresholds()
    below = plan.below if plan.below is not None else float(minimum)
    sf, labels = _student_filter(plan)
    db = get_db()
    q: dict[str, Any] = {"status": {"$ne": "archived"}}
    for key in ("programme_id", "year_of_study"):
        if key in sf:
            q[key] = sf[key]
    if "division_id" in sf:
        q["_id"] = sf["division_id"]
    rows = []
    for d in db.divisions.find(q):
        if not attendance.can_read_division(ctx, d):
            continue
        report = stats.division_report(ctx, str(d["_id"]), None, None)
        for s in report["students"]:
            if s["overall"] is not None and s["overall"] < below:
                rows.append(
                    {
                        "prn": s["prn"],
                        "student": s["name"],
                        "class": report["class"],
                        "percent": s["overall"],
                        "student_id": s["student_id"],
                    }
                )
    rows.sort(key=lambda r: r["percent"])
    scope = " ".join(labels) + " " if labels else ""
    return {
        "summary": f"{len(rows)} {scope}students are below {below:g}% attendance (in the classes you can see).",
        "count": len(rows),
        "columns": [
            ("prn", "PRN", "text"),
            ("student", "Student", "text"),
            ("class", "Class", "text"),
            ("percent", "Attendance %", "number"),
        ],
        "rows": rows,
        "link": "/app/attendance",
    }


def _certificates(ctx: AuthContext, plan: Plan) -> dict[str, Any]:
    from app.modules.certificates import service as certificates

    _need(ctx, P.CERT_MANAGE, P.CERT_READ)
    sf, labels = _student_filter(plan)
    db = get_db()
    q: dict[str, Any] = {"status": {"$in": list(certificates.OPEN)}}
    if plan.cert_type:
        q["type"] = plan.cert_type
    today = clock.today().isoformat()
    if plan.overdue_only:
        q["due_date"] = {"$lt": today}
    if len(sf) > 1:
        q["student_id"] = {"$in": [s["_id"] for s in db.students.find(sf, {"_id": 1})]}
    names: dict[Any, dict[str, Any]] = {}
    rows = []
    for r in db.certificate_requests.find(q).sort("due_date", 1).limit(MAX_ROWS + 1):
        v = certificates.view(r, names)
        rows.append(
            {
                "prn": v["prn"],
                "student": v["student"],
                "certificate": v["type_name"],
                "status": v["status_label"],
                "due": v["due_date"],
                "overdue": v["overdue"],
            }
        )
    kind = certificates.TYPES[plan.cert_type]["name"].lower() + " " if plan.cert_type else ""
    late = " past the promised date" if plan.overdue_only else ""
    scope = f" for {' '.join(labels)} students" if labels else ""
    return {
        "summary": f"{len(rows)} open {kind}certificate requests{late}{scope}.",
        "count": len(rows),
        "columns": [
            ("prn", "PRN", "text"),
            ("student", "Student", "text"),
            ("certificate", "Certificate", "text"),
            ("status", "Status", "text"),
            ("due", "Promised by", "date"),
        ],
        "rows": rows,
        "link": "/app/certificates",
    }


def _backlogs(ctx: AuthContext, plan: Plan) -> dict[str, Any]:
    from app.modules.results import service as results
    from app.modules.students import service as students

    _need(ctx, P.RESULTS_READ, P.MARKS_READ)
    sf, labels = _student_filter(plan)
    lookups = students._lookups()
    rows = []
    for s in get_db().students.find(sf).sort("prn", 1):
        b = results.standing(s["_id"])["backlogs"]
        if b:
            rows.append(
                {
                    "prn": s["prn"],
                    "student": s["name"],
                    "class": _class(s, lookups),
                    "subjects": ", ".join(x["code"] for x in b),
                    "count": len(b),
                    "student_id": str(s["_id"]),
                }
            )
    rows.sort(key=lambda r: -r["count"])
    scope = " ".join(labels) + " " if labels else ""
    return {
        "summary": f"{len(rows)} {scope}students have subjects still to clear "
        f"({sum(r['count'] for r in rows)} in all).",
        "count": len(rows),
        "columns": [
            ("prn", "PRN", "text"),
            ("student", "Student", "text"),
            ("class", "Class", "text"),
            ("subjects", "Subjects to clear", "text"),
        ],
        "rows": rows,
        "link": "/app/exams",
    }


RUN = {
    "fees_outstanding": _fees,
    "attendance_below": _attendance,
    "certificates_pending": _certificates,
    "backlogs": _backlogs,
}


def ask(ctx: AuthContext, question: str, ip: str) -> dict[str, Any]:
    if ctx.user.get("kind") != "staff":
        raise AppError(403, "The staff assistant is for college staff.", "forbidden")
    plan = _ai_plan(question) or parse(question)
    if plan.tool is None:
        return {
            "answered": False,
            "summary": "I can answer questions about fees outstanding, attendance below a percentage, open "
            "certificate requests and backlogs, for the whole college or one class.",
            "examples": EXAMPLES,
        }
    result = RUN[plan.tool](ctx, plan)
    rows = result["rows"]
    audit.record(
        "assistant.staff_query",
        actor_id=ctx.user_id,
        target_type="assistant",
        ip=ip,
        details={
            "query": plan.tool,
            "programme": plan.programme,
            "year": plan.year,
            "division": plan.division,
            "count": result["count"],
        },
    )
    return {
        "answered": True,
        "query": plan.tool,
        "filters": {
            k: v
            for k, v in {
                "programme": plan.programme,
                "year": plan.year,
                "division": plan.division,
                "above": format_inr(plan.min_amount, "₹") if plan.min_amount is not None else None,
                "overdue_only": plan.overdue_only or None,
                "below_percent": plan.below,
                "certificate": plan.cert_type,
            }.items()
            if v is not None
        },
        **{k: v for k, v in result.items() if k != "rows"},
        "columns": [{"key": k, "label": label, "type": t} for k, label, t in result["columns"]],
        "rows": rows[:MAX_ROWS],
        "more": max(0, len(rows) - MAX_ROWS),
    }
