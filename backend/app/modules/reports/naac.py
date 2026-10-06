"""
NAAC-ready by default (spec U8, plan 4.1).

Each NAAC metric that CollegeConnect has data for is computed from the records themselves for a
chosen academic year: its value, the table the AQAR asks for, and the gaps that would weaken it
("2 teachers have no qualifications recorded"). Metrics the system doesn't track yet are listed
as manual, so the IQAC knows to upload their data sheet. Each metric names the evidence NAAC
expects; the IQAC uploads it here, and a metric without evidence shows as a gap.

Metric numbers follow the NAAC framework for affiliated colleges (AQAR).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from statistics import median
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.files import save as save_file
from app.modules.grievance.service import SENSITIVE
from app.modules.reports import common
from app.modules.reports.schemas import NaacSettings
from app.modules.students import service as students

register_indexes("naac_evidence", [IndexModel([("year_id", ASCENDING), ("metric", ASCENDING)])])

SETTINGS_ID = "naac"
Columns = list[tuple[str, str]]
Result = dict[str, Any]


def settings() -> dict[str, Any]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID}) or {}
    return {"sanctioned_posts": doc.get("sanctioned_posts"), "intake": doc.get("intake", {})}


def save_settings(ctx: AuthContext, body: NaacSettings) -> dict[str, Any]:
    data = body.model_dump()
    get_db().settings.update_one({"_id": SETTINGS_ID}, {"$set": data}, upsert=True)
    audit.record("naac.settings_updated", actor_id=ctx.user_id, details=data)
    return settings()


# --- metrics --------------------------------------------------------------------------------


def _out(value: str, columns: Columns, rows: list[dict[str, Any]], gaps: list[str]) -> Result:
    return {"value": value, "columns": [{"key": k, "label": label} for k, label in columns], "rows": rows, "gaps": gaps}


def _admitted(y: dict[str, Any]) -> list[dict[str, Any]]:
    """First-year students admitted in this academic year (by admission date, else when the
    record was created)."""
    first, last = common.span(y)
    query = {
        "year_of_study": 1,
        "status": {"$nin": ["cancelled"]},
        "$or": [
            {"admission_date": {"$gte": y["start_date"], "$lte": y["end_date"]}},
            {"admission_date": None, "created_at": {"$gte": first, "$lt": last}},
        ],
    }
    return list(get_db().students.find(query, {"programme_id": 1, "category_id": 1}))


def cycle_seats(y: dict[str, Any]) -> dict[ObjectId, dict[str, Any]]:
    seats: dict[ObjectId, dict[str, Any]] = {}
    for c in get_db().admission_cycles.find({"academic_year_id": y["_id"]}, {"programmes": 1}):
        for p in c.get("programmes", []):
            if p.get("year_of_study", 1) == 1:
                seats[p["programme_id"]] = p
    return seats


def programmes_offered(y: dict[str, Any]) -> Result:
    rows = [
        {"code": p["code"], "name": p["name"], "level": p.get("level", ""), "years": p.get("duration_years")}
        for p in common.programmes().values()
    ]
    return _out(
        str(len(rows)), [("code", "Code"), ("name", "Programme"), ("level", "Level"), ("years", "Years")], rows, []
    )


def enrolment(y: dict[str, Any]) -> Result:
    progs = common.programmes()
    seats = cycle_seats(y)
    manual = settings()["intake"]
    admitted = _admitted(y)
    rows, gaps = [], []
    total_seats = total_admitted = 0
    for pid, p in progs.items():
        intake = seats[pid]["seats"] if pid in seats else manual.get(str(pid))
        n = sum(1 for s in admitted if s.get("programme_id") == pid)
        if not intake:
            gaps.append(f"No sanctioned intake for {p['code']}: set it in the NAAC settings or run admissions here.")
        else:
            total_seats += intake
            total_admitted += n
        rows.append({"programme": p["code"], "intake": intake, "admitted": n, "percent": common.pct(n, intake or 0)})
    value = f"{common.pct(total_admitted, total_seats)}%" if total_seats else "—"
    cols = [("programme", "Programme"), ("intake", "Sanctioned intake"), ("admitted", "Admitted"), ("percent", "%")]
    return _out(value, cols, rows, gaps)


def reserved_seats(y: dict[str, Any]) -> Result:
    cats = {c["_id"]: c for c in get_db().categories.find({}, {"code": 1, "name": 1})}
    reserved: dict[str, int] = {}
    for p in cycle_seats(y).values():
        for cid, n in p.get("reserved", {}).items():
            reserved[cid] = reserved.get(cid, 0) + n
    admitted = _admitted(y)
    rows, gaps = [], []
    for cid, c in cats.items():
        if c["code"] == "OPEN":
            continue
        n = sum(1 for s in admitted if s.get("category_id") == cid)
        rows.append({"category": c["code"], "reserved": reserved.get(str(cid), 0), "admitted": n})
    missing = sum(1 for s in admitted if not s.get("category_id"))
    if missing:
        gaps.append(f"{missing} admitted student(s) have no category recorded.")
    if not reserved:
        gaps.append("No reserved seats recorded for this year's admissions.")
    filled = sum(min(r["admitted"], r["reserved"]) for r in rows)
    value = f"{filled}/{sum(r['reserved'] for r in rows)} seats" if reserved else "—"
    return _out(value, [("category", "Category"), ("reserved", "Seats reserved"), ("admitted", "Admitted")], rows, gaps)


def student_teacher_ratio(y: dict[str, Any]) -> Result:
    teachers, missing = common.teachers()
    full_time = [t for t in teachers if t.get("employment") == "permanent"]
    n_students = get_db().students.count_documents({"status": "active"})
    gaps = [f"{missing} teaching account(s) have no staff record."] if missing else []
    value = f"{round(n_students / len(full_time))}:1" if full_time else "—"
    if not full_time:
        gaps.append("No full-time (permanent) teachers recorded.")
    rows = [{"students": n_students, "full_time_teachers": len(full_time), "all_teachers": len(teachers)}]
    cols = [("students", "Students"), ("full_time_teachers", "Full-time teachers"), ("all_teachers", "All teachers")]
    return _out(value, cols, rows, gaps)


def teachers_against_posts(y: dict[str, Any]) -> Result:
    teachers, missing = common.teachers()
    full_time = [t for t in teachers if t.get("employment") == "permanent"]
    posts = settings()["sanctioned_posts"]
    gaps = []
    if not posts:
        gaps.append("Sanctioned teaching posts are not set: add them in the NAAC settings.")
    if missing:
        gaps.append(f"{missing} teaching account(s) have no staff record.")
    no_order = [t["name"] for t in full_time if not t.get("appointment_order")]
    if no_order:
        gaps.append(f"{len(no_order)} full-time teacher(s) have no appointment order recorded: {', '.join(no_order)}.")
    rows = [
        {
            "name": t["name"],
            "designation": t.get("designation"),
            "employment": t.get("employment"),
            "appointment_order": t.get("appointment_order"),
            "university_approved": "Yes" if t.get("university_approved") else "No",
        }
        for t in sorted(teachers, key=lambda t: t["name"])
    ]
    value = f"{common.pct(len(full_time), posts)}%" if posts else f"{len(full_time)} full-time"
    cols = [
        ("name", "Teacher"),
        ("designation", "Designation"),
        ("employment", "Employment"),
        ("appointment_order", "Appointment order"),
        ("university_approved", "University approved"),
    ]
    return _out(value, cols, rows, gaps)


def teacher_qualifications(y: dict[str, Any]) -> Result:
    teachers, missing = common.teachers()
    rows, gaps = [], []
    none = []
    for t in sorted(teachers, key=lambda t: t["name"]):
        levels = {q["level"] for q in t.get("qualifications", [])}
        if not levels:
            none.append(t["name"])
        rows.append(
            {
                "name": t["name"],
                "highest": next((q["degree"] for q in t.get("qualifications", []) if q["level"] == "phd"), None)
                or next((q["degree"] for q in t.get("qualifications", []) if q["level"] == "pg"), None),
                "phd": "Yes" if "phd" in levels else "No",
                "net_set": "Yes" if levels & {"net", "set"} else "No",
            }
        )
    if none:
        gaps.append(f"{len(none)} teacher(s) have no qualifications recorded: {', '.join(none)}.")
    if missing:
        gaps.append(f"{missing} teaching account(s) have no staff record.")
    qualified = sum(1 for r in rows if r["phd"] == "Yes" or r["net_set"] == "Yes")
    value = f"{common.pct(qualified, len(rows))}%" if rows else "—"
    cols = [("name", "Teacher"), ("highest", "Highest qualification"), ("phd", "Ph.D."), ("net_set", "NET/SET")]
    return _out(value, cols, rows, gaps)


def pass_percentage(y: dict[str, Any]) -> Result:
    db = get_db()
    progs = common.programmes()
    rows, gaps = [], []
    appeared = passed = 0
    for pid, p in progs.items():
        final = p.get("duration_years")
        sessions = [
            s["_id"]
            for s in db.exam_sessions.find({"academic_year_id": y["_id"]}, {"classes": 1})
            if any(c["programme_id"] == pid and c["year_of_study"] == final for c in s.get("classes", []))
        ]
        results = list(db.results.find({"session_id": {"$in": sessions}}, {"student_id": 1, "outcome": 1}))
        by_student: dict[ObjectId, bool] = {}
        for r in results:
            by_student[r["student_id"]] = by_student.get(r["student_id"], True) and r.get("outcome") == "pass"
        a, ok = len(by_student), sum(by_student.values())
        appeared += a
        passed += ok
        if not sessions or not results:
            gaps.append(f"No final-year ({p['code']}) results imported for this year.")
        rows.append({"programme": p["code"], "appeared": a, "passed": ok, "percent": common.pct(ok, a)})
    value = f"{common.pct(passed, appeared)}%" if appeared else "—"
    cols = [("programme", "Programme"), ("appeared", "Appeared"), ("passed", "Passed"), ("percent", "%")]
    return _out(value, cols, rows, gaps)


def library_usage(y: dict[str, Any]) -> Result:
    db = get_db()
    loans = db.loans.count_documents({"issued_on": {"$gte": y["start_date"], "$lte": y["end_date"]}})
    titles = db.books.count_documents({})
    copies = db.book_copies.count_documents({"status": {"$nin": ["withdrawn", "lost"]}})
    gaps = [] if titles else ["The library catalogue is empty."]
    rows = [{"titles": titles, "copies": copies, "loans": loans, "per_day": round(loans / 250, 1)}]
    cols = [("titles", "Titles"), ("copies", "Copies"), ("loans", "Books issued"), ("per_day", "Per working day")]
    return _out(f"{loans} issues", cols, rows, gaps)


def scholarships(y: dict[str, Any]) -> Result:
    by_scheme: dict[str, dict[str, Any]] = {}
    for s in get_db().scholarships.find({"academic_year_id": y["_id"], "status": {"$in": ["sanctioned", "received"]}}):
        row = by_scheme.setdefault(s["scheme"], {"scheme": s["scheme"], "students": 0, "amount": 0})
        row["students"] += 1
        row["amount"] += s.get("sanctioned", 0)
    rows = [{**r, "amount": r["amount"] / 100} for r in sorted(by_scheme.values(), key=lambda r: r["scheme"])]
    total = len(
        {
            s["student_id"]
            for s in get_db().scholarships.find(
                {"academic_year_id": y["_id"], "status": {"$in": ["sanctioned", "received"]}}, {"student_id": 1}
            )
        }
    )
    n_students = get_db().students.count_documents({"status": "active"})
    gaps = [] if rows else ["No sanctioned scholarships recorded for this year."]
    value = f"{common.pct(total, n_students)}% ({total} students)" if n_students else "—"
    return _out(
        value, [("scheme", "Scheme"), ("students", "Students"), ("amount", "Amount sanctioned (Rs.)")], rows, gaps
    )


def grievances(y: dict[str, Any]) -> Result:
    first, last = common.span(y)
    rows_db = list(
        get_db().grievances.find(
            {"created_at": {"$gte": first, "$lt": last}}, {"category": 1, "status": 1, "resolved_at": 1, "due_date": 1}
        )
    )
    by_cat: dict[str, dict[str, Any]] = {}
    for g in rows_db:
        row = by_cat.setdefault(g["category"], {"category": g["category"], "received": 0, "resolved": 0, "in_time": 0})
        row["received"] += 1
        if g.get("resolved_at"):
            row["resolved"] += 1
            row["in_time"] += int(g["resolved_at"].astimezone(clock.IST).date().isoformat() <= g["due_date"])
    rows = sorted(by_cat.values(), key=lambda r: r["category"])
    resolved = sum(r["resolved"] for r in rows)
    gaps = []
    if not any(r["category"] in SENSITIVE for r in rows):
        gaps.append(
            "No ragging or harassment cases recorded: NAAC still asks for the committees' minutes (upload them)."
        )
    value = f"{resolved}/{len(rows_db)} resolved" if rows_db else "0 received"
    cols = [
        ("category", "Category"),
        ("received", "Received"),
        ("resolved", "Resolved"),
        ("in_time", "Within time limit"),
    ]
    return _out(value, cols, rows, gaps)


def placement(y: dict[str, Any]) -> Result:
    db = get_db()
    first, last = common.span(y)
    progs = common.programmes()
    drives = {
        d["_id"]: d for d in db.drives.find({"created_at": {"$gte": first, "$lt": last}}, {"ctc_lpa": 1, "company": 1})
    }
    selected = list(
        db.drive_registrations.find(
            {"drive_id": {"$in": list(drives)}, "status": "selected"}, {"student_id": 1, "drive_id": 1}
        )
    )
    placed = {s["student_id"] for s in selected}
    rows, gaps = [], []
    outgoing_total = placed_total = 0
    for pid, p in progs.items():
        final = list(
            db.students.find(
                {
                    "programme_id": pid,
                    "year_of_study": p.get("duration_years"),
                    "status": {"$in": ["active", "graduated"]},
                },
                {"_id": 1},
            )
        )
        ids = {s["_id"] for s in final}
        n_placed = len(ids & placed)
        outgoing_total += len(ids)
        placed_total += n_placed
        rows.append(
            {
                "programme": p["code"],
                "outgoing": len(ids),
                "placed": n_placed,
                "percent": common.pct(n_placed, len(ids)),
            }
        )
    ctcs: list[float] = [drives[s["drive_id"]]["ctc_lpa"] for s in selected if drives[s["drive_id"]].get("ctc_lpa")]
    if not drives:
        gaps.append("No placement drives recorded this year.")
    value = f"{common.pct(placed_total, outgoing_total)}%" if outgoing_total else "—"
    if ctcs:
        value += f" · median {median(ctcs)} LPA"
    cols = [("programme", "Programme"), ("outgoing", "Outgoing students"), ("placed", "Placed"), ("percent", "%")]
    return _out(value, cols, rows, gaps)


def manual(y: dict[str, Any]) -> Result:
    return _out("Upload", [], [], ["Not tracked in CollegeConnect yet: upload the data sheet as evidence."])


Metric = tuple[str, int, str, list[str], Callable[[dict[str, Any]], Result]]
METRICS: list[Metric] = [
    ("1.2.1", 1, "Programmes offered", ["List of programmes with university affiliation letters"], programmes_offered),
    (
        "2.1.1",
        2,
        "Enrolment against sanctioned intake",
        ["Sanctioned intake letter from the university / government"],
        enrolment,
    ),
    (
        "2.1.2",
        2,
        "Seats filled against reserved categories",
        ["Government reservation policy letter", "Admission list"],
        reserved_seats,
    ),
    ("2.2.2", 2, "Student – full-time teacher ratio", [], student_teacher_ratio),
    (
        "2.4.1",
        2,
        "Full-time teachers against sanctioned posts",
        ["Sanctioned posts letter", "Appointment orders"],
        teachers_against_posts,
    ),
    (
        "2.4.2",
        2,
        "Full-time teachers with Ph.D. / NET / SET",
        ["Copies of Ph.D. / NET / SET certificates"],
        teacher_qualifications,
    ),
    ("2.6.3", 2, "Pass percentage of final-year students", ["University result sheets"], pass_percentage),
    ("4.2.4", 4, "Library usage", ["Library issue register summary"], library_usage),
    ("5.1.1", 5, "Students benefited by government scholarships", ["Sanction letters / MahaDBT reports"], scholarships),
    (
        "5.1.5",
        5,
        "Grievance redressal, incl. sexual harassment and ragging",
        ["Committee constitution and minutes"],
        grievances,
    ),
    ("5.2.1", 5, "Placement of outgoing students", ["Offer letters", "Placement drive notices"], placement),
    ("5.2.2", 5, "Progression to higher education", ["List of students in higher education with proof"], manual),
    ("3.3.1", 3, "Research papers published by teachers", ["List of papers with links"], manual),
    ("7.1.1", 7, "Gender equity programmes", ["Reports of the programmes with photos"], manual),
]
CRITERIA = {
    1: "Curricular aspects",
    2: "Teaching-learning and evaluation",
    3: "Research, innovations and extension",
    4: "Infrastructure and learning resources",
    5: "Student support and progression",
    6: "Governance, leadership and management",
    7: "Institutional values and best practices",
}


def _metric(metric_id: str) -> Metric:
    m = next((m for m in METRICS if m[0] == metric_id), None)
    if not m:
        raise AppError(404, "Unknown NAAC metric.")
    return m


def _evidence(year_id: ObjectId) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for e in get_db().naac_evidence.find({"year_id": year_id}).sort("at", ASCENDING):
        out.setdefault(e["metric"], []).append(
            {"id": str(e["_id"]), "title": e["title"], "filename": e["filename"], "at": e["at"]}
        )
    return out


def compute(m: Metric, y: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    metric_id, criterion, title, needed, fn = m
    out = fn(y)
    gaps = list(out["gaps"])
    if needed and not evidence:
        gaps.append("No evidence uploaded yet (" + "; ".join(needed) + ").")
    return {
        "id": metric_id,
        "criterion": criterion,
        "criterion_name": CRITERIA[criterion],
        "title": title,
        "manual": fn is manual,
        "evidence_needed": needed,
        "evidence": evidence,
        **out,
        "gaps": gaps,
    }


def aqar(year_id: str | None) -> dict[str, Any]:
    """Every metric for the year: the AQAR tables and the gaps report in one call."""
    y = common.year(year_id)
    evidence = _evidence(y["_id"])
    metrics = [compute(m, y, evidence.get(m[0], [])) for m in METRICS]
    return {
        "year": {"id": str(y["_id"]), "name": y["name"]},
        "generated_at": datetime.now(UTC),
        "metrics": metrics,
        "gaps": sum(len(m["gaps"]) for m in metrics),
        "settings": settings(),
    }


def metric_csv(metric_id: str, year_id: str | None) -> tuple[str, str]:
    m = _metric(metric_id)
    y = common.year(year_id)
    out = m[4](y)
    cols = [(c["key"], c["label"]) for c in out["columns"]]
    return common.to_csv(cols, out["rows"]), f"naac-{metric_id}-{y['name']}.csv"


def add_evidence(
    ctx: AuthContext, metric_id: str, year_id: str | None, title: str, data: bytes, filename: str
) -> dict[str, Any]:
    _metric(metric_id)
    y = common.year(year_id)
    f = save_file(data, filename=filename, student_id=None, purpose="naac", created_by=ctx.user_id)
    doc = {
        "year_id": y["_id"],
        "metric": metric_id,
        "title": title.strip() or filename,
        "file_id": f["_id"],
        "filename": f["filename"],
        "at": datetime.now(UTC),
        "by": ctx.user_id,
    }
    get_db().naac_evidence.insert_one(doc)
    audit.record(
        "naac.evidence_added",
        actor_id=ctx.user_id,
        details={"metric": metric_id, "year": y["name"], "title": doc["title"]},
    )
    return {"id": str(doc["_id"]), "title": doc["title"], "filename": doc["filename"], "at": doc["at"]}


def evidence_file(evidence_id: str) -> dict[str, Any]:
    db = get_db()
    e = db.naac_evidence.find_one({"_id": students.oid(evidence_id, "Evidence")})
    if not e:
        raise AppError(404, "Evidence not found.")
    f = db.files.find_one({"_id": e["file_id"]})
    if not f:
        raise AppError(404, "Evidence not found.")
    return f


def remove_evidence(ctx: AuthContext, evidence_id: str) -> None:
    db = get_db()
    e = db.naac_evidence.find_one_and_delete({"_id": students.oid(evidence_id, "Evidence")})
    if not e:
        raise AppError(404, "Evidence not found.")
    db.files.delete_one({"_id": e["file_id"]})
    audit.record("naac.evidence_removed", actor_id=ctx.user_id, details={"metric": e["metric"], "title": e["title"]})
