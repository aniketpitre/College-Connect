"""
Exam forms and hall tickets (spec R6, plan 2.7).

The Exam Cell opens an exam session (e.g. "Oct–Nov 2026 university exams") for some classes and
a term, with a form deadline, the fee head that must be paid (EXAM by default) and the paper
timetable. Each student of those classes fills the form in their portal (their semester's
subjects, plus backlogs from 2.8). The Exam Cell sees who is eligible (attendance minimum in every
subject, fee paid), verifies or rejects forms, assigns seat numbers and exports the list for the
university portal. Hall tickets are made as PDFs on demand (nothing stored: MongoDB free tier).
"""

import contextlib
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.attendance import stats
from app.modules.exams.schemas import SessionIn, SessionUpdate
from app.modules.fees import ledger
from app.modules.marks import service as marks
from app.modules.timetable import service as timetable

register_indexes("exam_sessions", [IndexModel([("academic_year_id", ASCENDING), ("term", ASCENDING)])])
register_indexes(
    "exam_forms",
    [
        IndexModel([("session_id", ASCENDING), ("student_id", ASCENDING)], unique=True),
        IndexModel([("student_id", ASCENDING)]),
    ],
)

FORM_STATUS = {
    "not_submitted": "Not submitted",
    "submitted": "Submitted",
    "verified": "Verified",
    "rejected": "Rejected",
}


def _require_manage(ctx: AuthContext) -> None:
    if P.EXAMS_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell manages exams.", "forbidden")


def get_session(session_id: str) -> dict[str, Any]:
    s = get_db().exam_sessions.find_one({"_id": timetable.oid(session_id, "Exam")})
    if not s:
        raise AppError(404, "Exam not found.")
    return s


def _semester(programme: dict[str, Any], year_of_study: int, term: int) -> int:
    return (year_of_study - 1) * programme["semesters_per_year"] + term


def students_in(session: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    ors = [{"programme_id": c["programme_id"], "year_of_study": c["year_of_study"]} for c in session["classes"]]
    rows = list(
        db.students.find(
            {"status": "active", "$or": ors},
            {"name": 1, "prn": 1, "programme_id": 1, "year_of_study": 1, "division_id": 1, "roll_no": 1},
        )
    )
    return sorted(rows, key=lambda s: s["prn"])


def regular_subjects(session: dict[str, Any], student: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    programme = db.programmes.find_one({"_id": student["programme_id"]}) or {"semesters_per_year": 2}
    sem = _semester(programme, student["year_of_study"], session["term"])
    return list(
        db.subjects.find(
            {"programme_id": student["programme_id"], "semester": sem, "status": {"$ne": "archived"}},
            {"code": 1, "name": 1, "credits": 1},
        ).sort("code", ASCENDING)
    )


# Results (2.8) add backlog subjects: fn(student_id) → [subject docs]
BACKLOG_SUBJECTS: list[Any] = []


def backlog_subjects(student_id: ObjectId, regular: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Subjects still to clear from earlier exams (not the ones already on this form)."""
    skip = {s["_id"] for s in regular or []}
    out: list[dict[str, Any]] = []
    for hook in BACKLOG_SUBJECTS:
        out += [s for s in hook(student_id) if s["_id"] not in skip]
    return out


def eligibility(session: dict[str, Any], students: list[dict[str, Any]]) -> dict[ObjectId, dict[str, Any]]:
    """student → {attendance_ok, low_subjects, fee_ok, fee_due}."""
    db = get_db()
    minimum, _ = stats.thresholds()
    ids = [s["_id"] for s in students]
    tallies = stats.tally(ids, {"academic_year_id": session["academic_year_id"]})
    subject_codes = {s["_id"]: s["code"] for s in db.subjects.find({}, {"code": 1})}
    head = db.fee_heads.find_one({"code": session.get("fee_head_code")}) if session.get("fee_head_code") else None
    out: dict[ObjectId, dict[str, Any]] = {}
    for s in students:
        low = [
            f"{subject_codes.get(sub, '?')} {round(r['attended'] * 100 / r['held'], 1)}%"
            for sub, r in tallies.get(s["_id"], {}).items()
            if r["held"] and r["attended"] * 100 / r["held"] < minimum
        ]
        due = 0
        if head:
            due = max(0, ledger.by_head(ledger.entries(s["_id"], session["academic_year_id"])).get(head["_id"], 0))
        out[s["_id"]] = {"attendance_ok": not low, "low_subjects": low, "fee_ok": due == 0, "fee_due": due}
    return out


def session_view(s: dict[str, Any], *, counts: bool = True) -> dict[str, Any]:
    db = get_db()
    programmes = {p["_id"]: p for p in db.programmes.find({}, {"code": 1, "year_labels": 1})}
    subjects = {
        x["_id"]: x
        for x in db.subjects.find(
            {"_id": {"$in": [p["subject_id"] for p in s.get("papers", [])]}}, {"code": 1, "name": 1}
        )
    }
    view: dict[str, Any] = {
        "id": str(s["_id"]),
        "name": s["name"],
        "kind": s["kind"],
        "term": s["term"],
        "academic_year_id": str(s["academic_year_id"]),
        "classes": [
            {
                "programme_id": str(c["programme_id"]),
                "year_of_study": c["year_of_study"],
                "label": f"{programmes.get(c['programme_id'], {}).get('code', '?')} "
                + (programmes.get(c["programme_id"], {}).get("year_labels") or ["?"] * 6)[c["year_of_study"] - 1],
            }
            for c in s["classes"]
        ],
        "form_deadline": s["form_deadline"],
        "form_open": clock.today().isoformat() <= s["form_deadline"],
        "fee_head_code": s.get("fee_head_code"),
        "seat_prefix": s.get("seat_prefix", ""),
        "papers": [
            {
                "subject_id": str(p["subject_id"]),
                "code": subjects.get(p["subject_id"], {}).get("code"),
                "name": subjects.get(p["subject_id"], {}).get("name"),
                "date": p["date"],
                "start": p["start"],
                "end": p["end"],
            }
            for p in sorted(s.get("papers", []), key=lambda p: (p["date"], p["start"]))
        ],
        "hall_tickets_released": bool(s.get("hall_tickets_released")),
    }
    if counts:
        expected = len(students_in(s))
        by_status = {
            r["_id"]: r["n"]
            for r in db.exam_forms.aggregate(
                [{"$match": {"session_id": s["_id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
            )
        }
        view["counts"] = {
            "students": expected,
            **{k: by_status.get(k, 0) for k in ("submitted", "verified", "rejected")},
        }
    return view


# --- Exam Cell ------------------------------------------------------------------------------


def create_session(ctx: AuthContext, body: SessionIn, ip: str) -> dict[str, Any]:
    _require_manage(ctx)
    db = get_db()
    year_id = marks.current_year_id()
    classes = []
    for c in body.classes:
        programme = db.programmes.find_one({"_id": timetable.oid(c.programme_id, "Programme", "classes")})
        if not programme or c.year_of_study > programme["duration_years"]:
            raise AppError(422, "Choose classes of existing programmes.", field="classes")
        if body.term > programme["semesters_per_year"]:
            raise AppError(
                422, f"{programme['code']} has {programme['semesters_per_year']} terms a year.", field="term"
            )
        classes.append({"programme_id": programme["_id"], "year_of_study": c.year_of_study})
    head_code = (body.fee_head_code or "").strip().upper() or None
    if head_code and not db.fee_heads.find_one({"code": head_code}):
        raise AppError(422, f"There is no fee head {head_code}.", field="fee_head_code")
    doc: dict[str, Any] = {
        "name": body.name.strip(),
        "kind": body.kind,
        "term": body.term,
        "academic_year_id": year_id,
        "classes": classes,
        "form_deadline": body.form_deadline.isoformat(),
        "fee_head_code": head_code,
        "seat_prefix": body.seat_prefix,
        "papers": [],
        "hall_tickets_released": False,
        "created_by": ctx.user_id,
        "created_at": clock.now(),
    }
    doc["_id"] = db.exam_sessions.insert_one(doc).inserted_id
    audit.record(
        "exams.session_created",
        actor_id=ctx.user_id,
        target_type="exam",
        target_id=doc["_id"],
        ip=ip,
        details={"name": doc["name"]},
    )
    return session_view(doc)


def update_session(ctx: AuthContext, session_id: str, body: SessionUpdate, ip: str) -> dict[str, Any]:
    _require_manage(ctx)
    s = get_session(session_id)
    db = get_db()
    changes: dict[str, Any] = {}
    if body.name is not None:
        changes["name"] = body.name.strip()
    if body.form_deadline is not None:
        changes["form_deadline"] = body.form_deadline.isoformat()
    if body.papers is not None:
        papers = []
        for p in body.papers:
            subject = db.subjects.find_one({"_id": timetable.oid(p.subject_id, "Subject", "papers")})
            if not subject:
                raise AppError(422, "Unknown subject in the timetable.", field="papers")
            papers.append({"subject_id": subject["_id"], "date": p.date.isoformat(), "start": p.start, "end": p.end})
        changes["papers"] = papers
    if body.hall_tickets_released is not None:
        if body.hall_tickets_released and not db.exam_forms.count_documents(
            {"session_id": s["_id"], "seat_no": {"$exists": True}}
        ):
            raise AppError(409, "Assign seat numbers before releasing hall tickets.", "no_seats")
        changes["hall_tickets_released"] = body.hall_tickets_released
    if changes:
        db.exam_sessions.update_one({"_id": s["_id"]}, {"$set": changes})
        audit.record(
            "exams.session_updated",
            actor_id=ctx.user_id,
            target_type="exam",
            target_id=s["_id"],
            ip=ip,
            details={k: (len(v) if k == "papers" else v) for k, v in changes.items()},
        )
    return session_view(get_session(session_id))


def list_sessions(ctx: AuthContext) -> list[dict[str, Any]]:
    if not ctx.permissions & {P.EXAMS_MANAGE, P.RESULTS_READ, P.MARKS_READ}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    rows = get_db().exam_sessions.find({}).sort("created_at", -1).limit(100)
    return [session_view(s) for s in rows]


def forms(ctx: AuthContext, session_id: str) -> list[dict[str, Any]]:
    if not ctx.permissions & {P.EXAMS_MANAGE, P.RESULTS_READ}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    s = get_session(session_id)
    db = get_db()
    students = students_in(s)
    elig = eligibility(s, students)
    by_student = {f["student_id"]: f for f in db.exam_forms.find({"session_id": s["_id"]})}
    divisions = {d["_id"]: d for d in db.divisions.find({})}
    out = []
    for st in students:
        f = by_student.get(st["_id"])
        e = elig[st["_id"]]
        division = divisions.get(st.get("division_id"))
        out.append(
            {
                "student_id": str(st["_id"]),
                "name": st["name"],
                "prn": st["prn"],
                "class": timetable._division_label(division) if division else None,
                "status": f["status"] if f else "not_submitted",
                "status_label": FORM_STATUS[f["status"] if f else "not_submitted"],
                "subjects": [x["code"] for x in (f or {}).get("subjects", [])],
                "backlogs": [x["code"] for x in (f or {}).get("subjects", []) if x.get("backlog")],
                "seat_no": (f or {}).get("seat_no"),
                "reason": (f or {}).get("reason"),
                **e,
                "eligible": e["attendance_ok"] and e["fee_ok"],
            }
        )
    return out


def verify(
    ctx: AuthContext, session_id: str, student_id: str, approve: bool, reason: str | None, ip: str
) -> dict[str, Any]:
    _require_manage(ctx)
    s = get_session(session_id)
    db = get_db()
    sid = timetable.oid(student_id, "Student")
    form = db.exam_forms.find_one({"session_id": s["_id"], "student_id": sid})
    if not form or form["status"] == "not_submitted":
        raise AppError(409, "The student hasn't submitted the form.", "not_submitted")
    student = db.students.find_one({"_id": sid})
    e = eligibility(s, [student])[sid] if student else {"attendance_ok": False, "fee_ok": False}
    if approve and not (e["attendance_ok"] and e["fee_ok"]) and not (reason and reason.strip()):
        raise AppError(
            422, "The student isn't eligible; give a reason to verify anyway (e.g. condonation).", field="reason"
        )
    if not approve and not (reason and reason.strip()):
        raise AppError(422, "Give a reason for rejecting.", field="reason")
    db.exam_forms.update_one(
        {"_id": form["_id"]},
        {
            "$set": {
                "status": "verified" if approve else "rejected",
                "reason": (reason or "").strip() or None,
                "verified_by": ctx.user_id,
                "verified_at": clock.now(),
            }
        },
    )
    audit.record(
        f"exams.form_{'verified' if approve else 'rejected'}",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=sid,
        ip=ip,
        reason=reason,
        details={"exam": s["name"]},
    )
    return next(r for r in forms(ctx, session_id) if r["student_id"] == student_id)


def verify_eligible(ctx: AuthContext, session_id: str, ip: str) -> dict[str, int]:
    """Verifies every submitted form whose student is eligible."""
    _require_manage(ctx)
    s = get_session(session_id)
    db = get_db()
    submitted = list(db.exam_forms.find({"session_id": s["_id"], "status": "submitted"}, {"student_id": 1}))
    students = list(db.students.find({"_id": {"$in": [f["student_id"] for f in submitted]}}))
    elig = eligibility(s, students)
    ok = [sid for sid, e in elig.items() if e["attendance_ok"] and e["fee_ok"]]
    if ok:
        db.exam_forms.update_many(
            {"session_id": s["_id"], "student_id": {"$in": ok}, "status": "submitted"},
            {"$set": {"status": "verified", "verified_by": ctx.user_id, "verified_at": clock.now()}},
        )
    audit.record(
        "exams.forms_verified",
        actor_id=ctx.user_id,
        target_type="exam",
        target_id=s["_id"],
        ip=ip,
        details={"verified": len(ok)},
    )
    return {"verified": len(ok), "left": len(submitted) - len(ok)}


def assign_seats(ctx: AuthContext, session_id: str, ip: str) -> dict[str, int]:
    """Seat numbers for verified forms, in PRN order, continuing after any already given."""
    _require_manage(ctx)
    s = get_session(session_id)
    db = get_db()
    verified = list(db.exam_forms.find({"session_id": s["_id"], "status": "verified"}))
    taken = [f["seat_no"] for f in verified if f.get("seat_no")]
    prns = {
        x["_id"]: x["prn"] for x in db.students.find({"_id": {"$in": [f["student_id"] for f in verified]}}, {"prn": 1})
    }
    n = len(taken)
    given = 0
    for f in sorted((f for f in verified if not f.get("seat_no")), key=lambda f: prns.get(f["student_id"], "")):
        n += 1
        db.exam_forms.update_one({"_id": f["_id"]}, {"$set": {"seat_no": f"{s.get('seat_prefix', '')}{n:04d}"}})
        given += 1
    audit.record(
        "exams.seats_assigned",
        actor_id=ctx.user_id,
        target_type="exam",
        target_id=s["_id"],
        ip=ip,
        details={"assigned": given},
    )
    return {"assigned": given, "total": n}


def export_csv(ctx: AuthContext, session_id: str) -> tuple[str, bytes]:
    import csv
    import io

    rows = forms(ctx, session_id)
    s = get_session(session_id)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        ["PRN", "Name", "Class", "Seat no", "Form", "Subjects", "Backlogs", "Attendance OK", "Fee paid", "Eligible"]
    )
    yes = lambda v: "Yes" if v else "No"  # noqa: E731
    for r in rows:
        w.writerow(
            [
                r["prn"],
                r["name"],
                r["class"],
                r["seat_no"] or "",
                r["status_label"],
                " ".join(r["subjects"]),
                " ".join(r["backlogs"]),
                yes(r["attendance_ok"]),
                yes(r["fee_ok"]),
                yes(r["eligible"]),
            ]
        )
    return f"exam-forms-{s['name'][:40].replace(' ', '-')}.csv", ("﻿" + out.getvalue()).encode("utf-8")


# --- student --------------------------------------------------------------------------------


def _my_view(s: dict[str, Any], student: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    form = db.exam_forms.find_one({"session_id": s["_id"], "student_id": student["_id"]})
    stored = [{k: v for k, v in x.items() if k != "subject_id"} for x in (form or {}).get("subjects", [])]
    regular = regular_subjects(s, student)
    subjects = stored or [{"code": x["code"], "name": x["name"]} for x in regular] + [
        {"code": x["code"], "name": x["name"], "backlog": True} for x in backlog_subjects(student["_id"], regular)
    ]
    e = eligibility(s, [student])[student["_id"]]
    v = session_view(s, counts=False)
    return {
        **v,
        "form_status": form["status"] if form else "not_submitted",
        "subjects": subjects,
        "seat_no": (form or {}).get("seat_no"),
        "reason": (form or {}).get("reason"),
        "attendance_ok": e["attendance_ok"],
        "low_subjects": e["low_subjects"],
        "fee_ok": e["fee_ok"],
        "fee_due": e["fee_due"],
        "hall_ticket": bool(
            v["hall_tickets_released"] and form and form["status"] == "verified" and form.get("seat_no")
        ),
    }


def _my_sessions(student: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        get_db()
        .exam_sessions.find(
            {
                "classes": {
                    "$elemMatch": {"programme_id": student["programme_id"], "year_of_study": student["year_of_study"]}
                }
            }
        )
        .sort("created_at", -1)
    )


def my_exams(ctx: AuthContext) -> list[dict[str, Any]]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    db = get_db()
    today = clock.today().isoformat()
    shown = []
    for s in _my_sessions(student):
        # A closed exam the student never had a form for is just noise in their list.
        if today > s["form_deadline"] and not db.exam_forms.find_one(
            {"session_id": s["_id"], "student_id": student["_id"]}, {"_id": 1}
        ):
            continue
        shown.append(_my_view(s, student))
    return shown


def submit_form(ctx: AuthContext, session_id: str, ip: str) -> dict[str, Any]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    s = get_session(session_id)
    if s["_id"] not in {x["_id"] for x in _my_sessions(student)}:
        raise AppError(404, "Exam not found.")
    if clock.today().isoformat() > s["form_deadline"]:
        raise AppError(409, "The last date for the exam form has passed. Contact the Exam Cell.", "form_closed")
    db = get_db()
    existing = db.exam_forms.find_one({"session_id": s["_id"], "student_id": student["_id"]})
    if existing and existing["status"] in ("verified",):
        raise AppError(409, "Your form is already verified.", "conflict")
    regular = regular_subjects(s, student)
    subjects = [{"subject_id": x["_id"], "code": x["code"], "name": x["name"]} for x in regular] + [
        {"subject_id": x["_id"], "code": x["code"], "name": x["name"], "backlog": True}
        for x in backlog_subjects(student["_id"], regular)
    ]
    if not subjects:
        raise AppError(409, "No subjects are set for your semester yet. Contact the Exam Cell.", "no_subjects")
    doc = {"status": "submitted", "subjects": subjects, "submitted_at": clock.now(), "reason": None}
    with contextlib.suppress(DuplicateKeyError):  # two taps at once: one of them wins
        db.exam_forms.update_one(
            {"session_id": s["_id"], "student_id": student["_id"]},
            {"$set": doc, "$setOnInsert": {"created_at": clock.now()}},
            upsert=True,
        )
    audit.record(
        "exams.form_submitted",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"exam": s["name"]},
    )
    return _my_view(s, student)


def hall_ticket_data(session_id: str, student_id: ObjectId) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    db = get_db()
    s = get_session(session_id)
    form = db.exam_forms.find_one({"session_id": s["_id"], "student_id": student_id})
    if not form or form["status"] != "verified" or not form.get("seat_no"):
        raise AppError(409, "No hall ticket: the form isn't verified or has no seat number yet.", "no_hall_ticket")
    student = db.students.find_one({"_id": student_id})
    assert student is not None
    return s, form, student


def my_hall_ticket(ctx: AuthContext, session_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    s, form, st = hall_ticket_data(session_id, student["_id"])
    if not s.get("hall_tickets_released"):
        raise AppError(409, "Hall tickets aren't released yet.", "not_released")
    return s, form, st


# Upload Guard: a student without a verified form for this term's university exam isn't eligible.
def _guard_hook(division_id: ObjectId, subject_id: ObjectId, student_ids: list[ObjectId]) -> dict[ObjectId, str]:
    db = get_db()
    subject = db.subjects.find_one({"_id": subject_id}, {"programme_id": 1, "semester": 1})
    programme = db.programmes.find_one({"_id": (subject or {}).get("programme_id")}, {"semesters_per_year": 1})
    if not subject or not programme:
        return {}
    spy = programme["semesters_per_year"]
    year_of_study, term = (subject["semester"] - 1) // spy + 1, (subject["semester"] - 1) % spy + 1
    session = db.exam_sessions.find_one(
        {
            "kind": "university",
            "academic_year_id": marks.current_year_id(),
            "term": term,
            "classes": {"$elemMatch": {"programme_id": subject["programme_id"], "year_of_study": year_of_study}},
        }
    )
    if not session or clock.today().isoformat() <= session["form_deadline"]:
        return {}
    verified = {
        f["student_id"]
        for f in db.exam_forms.find({"session_id": session["_id"], "status": "verified"}, {"student_id": 1})
    }
    return {sid: "Exam form not verified" for sid in student_ids if sid not in verified}


def register_hooks() -> None:
    from app.modules.marks import guard

    if _guard_hook not in guard.EXTRA_ELIGIBILITY:
        guard.EXTRA_ELIGIBILITY.append(_guard_hook)


register_hooks()
