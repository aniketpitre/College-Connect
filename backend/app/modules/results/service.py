"""
University results (spec §3.8, plan 2.8).

The Exam Cell imports the university's result file for an exam (one row per student and paper:
PRN, subject code, internal, external, total, grade, grade points, credits, result), checks the
preview, then imports it: one `results` document per student and exam. Publishing makes them
visible to students, with a revaluation window.

- Grade points on the UGC 10-point scale when the file has none (O 10, A+ 9, A 8, B+ 7, B 6,
  C 5, P 4, F/AB 0).
- SGPA = Σ(credits × grade points) / Σ credits of the exam's papers.
- CGPA uses each subject's latest attempt over all exams; a backlog is a subject whose latest
  attempt was not passed. Backlogs are added to the next exam form automatically.
"""

from collections import defaultdict
from datetime import timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel, UpdateOne
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.exams import service as exams
from app.modules.students.importer import read_rows
from app.modules.timetable.service import oid

register_indexes(
    "results",
    [
        IndexModel([("session_id", ASCENDING), ("student_id", ASCENDING)], unique=True),
        IndexModel([("student_id", ASCENDING), ("exam_order", ASCENDING)]),
    ],
)
register_indexes(
    "revaluations",
    [
        IndexModel([("status", ASCENDING), ("requested_at", ASCENDING)]),
        IndexModel([("result_id", ASCENDING), ("code", ASCENDING)], unique=True),
    ],
)

GRADE_POINTS = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0, "AB": 0}
FAILED = {"F", "AB"}
REVAL_STATUS = {
    "requested": "Requested",
    "forwarded": "Sent to the university",
    "changed": "Marks changed",
    "unchanged": "No change",
}


def _require_manage(ctx: AuthContext) -> None:
    if P.EXAMS_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the Exam Cell manages results.", "forbidden")


def _num(value: str, what: str, problems: list[str], n: int) -> float | None:
    if value in ("", "-"):
        return None
    if value.upper() == "AB":
        return None
    try:
        return float(value)
    except ValueError:
        problems.append(f"Row {n}: {what} '{value}' is not a number.")
        return None


def sgpa(subjects: list[dict[str, Any]]) -> float | None:
    credits = sum(s["credits"] for s in subjects)
    if not credits:
        return None
    return round(sum(s["credits"] * s["grade_point"] for s in subjects) / credits, 2)


def outcome(subjects: list[dict[str, Any]]) -> str:
    if subjects and all(s["grade"] == "AB" for s in subjects):
        return "absent"
    return "pass" if all(s["passed"] for s in subjects) else "atkt"


# --- import ---------------------------------------------------------------------------------


def _parse(filename: str, data: bytes) -> tuple[dict[ObjectId, list[dict[str, Any]]], list[str], dict[str, Any]]:
    db = get_db()
    rows = read_rows(filename, data, required=("prn", "subject_code", "grade"))
    problems: list[str] = []
    students = {
        s["prn"]: s
        for s in db.students.find(
            {"prn": {"$in": [r.get("prn", "").upper() for r in rows]}}, {"prn": 1, "name": 1, "programme_id": 1}
        )
    }
    subjects = {
        s["code"]: s for s in db.subjects.find({"code": {"$in": [r.get("subject_code", "").upper() for r in rows]}})
    }
    by_student: dict[ObjectId, list[dict[str, Any]]] = defaultdict(list)
    for n, r in enumerate(rows, start=2):
        prn, code, grade = r.get("prn", "").upper(), r.get("subject_code", "").upper(), r.get("grade", "").upper()
        student, subject = students.get(prn), subjects.get(code)
        if not student:
            problems.append(f"Row {n}: no student with PRN {prn}.")
            continue
        if not subject or subject["programme_id"] != student["programme_id"]:
            problems.append(f"Row {n}: {code} is not a subject of {prn}'s programme.")
            continue
        gp_raw = r.get("grade_points", "")
        if grade not in GRADE_POINTS and not gp_raw:
            problems.append(f"Row {n}: unknown grade {grade or '(empty)'}; add a grade_points column for other scales.")
            continue
        gp = _num(gp_raw, "grade points", problems, n)
        credits = _num(r.get("credits", ""), "credits", problems, n)
        result_col = r.get("result", "").strip().upper()
        passed = result_col in ("P", "PASS") if result_col else grade not in FAILED
        if any(x["code"] == code for x in by_student[student["_id"]]):
            problems.append(f"Row {n}: {prn} has {code} twice.")
            continue
        by_student[student["_id"]].append(
            {
                "subject_id": subject["_id"],
                "code": code,
                "name": subject["name"],
                "semester": subject["semester"],
                "credits": credits if credits is not None else subject.get("credits", 0),
                "internal": _num(r.get("internal", ""), "internal", problems, n),
                "external": _num(r.get("external", ""), "external", problems, n),
                "total": _num(r.get("total", ""), "total", problems, n),
                "grade": grade,
                "grade_point": gp if gp is not None else GRADE_POINTS.get(grade, 0),
                "passed": passed,
            }
        )
    summary = {
        "rows": len(rows),
        "students": len(by_student),
        "pass": sum(1 for v in by_student.values() if outcome(v) == "pass"),
        "atkt": sum(1 for v in by_student.values() if outcome(v) == "atkt"),
    }
    return by_student, problems, summary


def import_results(
    ctx: AuthContext, session_id: str, filename: str, data: bytes, dry_run: bool, ip: str
) -> dict[str, Any]:
    _require_manage(ctx)
    session = exams.get_session(session_id)
    if session.get("results_published") and not dry_run:
        raise AppError(409, "Results are published. Withdraw them before importing again.", "published")
    by_student, problems, summary = _parse(filename, data)
    if dry_run or problems:
        return {**summary, "problems": problems[:200], "imported": False}
    db = get_db()
    order = int(session["created_at"].timestamp())
    ops = []
    for sid, subjects in by_student.items():
        semesters = sorted({s["semester"] for s in subjects})
        ops.append(
            UpdateOne(
                {"session_id": session["_id"], "student_id": sid},
                {
                    "$set": {
                        "subjects": subjects,
                        "semesters": semesters,
                        "sgpa": sgpa(subjects),
                        "credits": sum(s["credits"] for s in subjects),
                        "credits_earned": sum(s["credits"] for s in subjects if s["passed"]),
                        "outcome": outcome(subjects),
                        "exam_order": order,
                        "imported_at": clock.now(),
                        "imported_by": ctx.user_id,
                    }
                },
                upsert=True,
            )
        )
    if ops:
        db.results.bulk_write(ops, ordered=False)
    audit.record(
        "results.imported", actor_id=ctx.user_id, target_type="exam", target_id=session["_id"], ip=ip, details=summary
    )
    return {**summary, "problems": [], "imported": True}


def publish(ctx: AuthContext, session_id: str, publish: bool, revaluation_days: int, ip: str) -> dict[str, Any]:
    _require_manage(ctx)
    session = exams.get_session(session_id)
    db = get_db()
    if publish and not db.results.count_documents({"session_id": session["_id"]}):
        raise AppError(409, "Import the results first.", "no_results")
    changes: dict[str, Any] = {"results_published": publish}
    if publish:
        changes["revaluation_until"] = (clock.today() + timedelta(days=revaluation_days)).isoformat()
        changes["results_published_at"] = clock.now()
    db.exam_sessions.update_one({"_id": session["_id"]}, {"$set": changes})
    audit.record(
        f"results.{'published' if publish else 'withdrawn'}",
        actor_id=ctx.user_id,
        target_type="exam",
        target_id=session["_id"],
        ip=ip,
    )
    return summary(ctx, session_id)


def summary(ctx: AuthContext, session_id: str) -> dict[str, Any]:
    if not ctx.permissions & {P.EXAMS_MANAGE, P.RESULTS_READ}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    session = exams.get_session(session_id)
    db = get_db()
    rows = list(db.results.find({"session_id": session["_id"]}))
    students = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}}, {"name": 1, "prn": 1})
    }
    out = sorted(
        (
            {
                "result_id": str(r["_id"]),
                "student_id": str(r["student_id"]),
                "name": students.get(r["student_id"], {}).get("name"),
                "prn": students.get(r["student_id"], {}).get("prn"),
                "sgpa": r["sgpa"],
                "outcome": r["outcome"],
                "failed": [s["code"] for s in r["subjects"] if not s["passed"]],
            }
            for r in rows
        ),
        key=lambda x: x["prn"] or "",
    )
    return {
        "published": bool(session.get("results_published")),
        "revaluation_until": session.get("revaluation_until"),
        "students": out,
        "counts": {k: sum(1 for r in out if r["outcome"] == k) for k in ("pass", "atkt", "absent")},
    }


# --- per student ----------------------------------------------------------------------------


def _attempts(student_id: ObjectId, published_only: bool) -> list[dict[str, Any]]:
    db = get_db()
    rows = list(db.results.find({"student_id": student_id}).sort("exam_order", ASCENDING))
    if published_only:
        published = {
            s["_id"]
            for s in db.exam_sessions.find(
                {"_id": {"$in": [r["session_id"] for r in rows]}, "results_published": True}, {"_id": 1}
            )
        }
        rows = [r for r in rows if r["session_id"] in published]
    return rows


def standing(student_id: ObjectId, published_only: bool = True) -> dict[str, Any]:
    """CGPA over each subject's latest attempt, and the subjects still to clear."""
    latest: dict[ObjectId, dict[str, Any]] = {}
    for r in _attempts(student_id, published_only):
        for s in r["subjects"]:
            latest[s["subject_id"]] = s
    subjects = list(latest.values())
    return {
        "cgpa": sgpa(subjects),
        "credits_earned": sum(s["credits"] for s in subjects if s["passed"]),
        "backlogs": sorted(
            (
                {"subject_id": s["subject_id"], "code": s["code"], "name": s["name"], "semester": s["semester"]}
                for s in subjects
                if not s["passed"]
            ),
            key=lambda x: x["code"],
        ),
    }


def _backlog_hook(student_id: ObjectId) -> list[dict[str, Any]]:
    ids = [b["subject_id"] for b in standing(student_id)["backlogs"]]
    return list(
        get_db().subjects.find({"_id": {"$in": ids}}, {"code": 1, "name": 1, "credits": 1}).sort("code", ASCENDING)
    )


if _backlog_hook not in exams.BACKLOG_SUBJECTS:
    exams.BACKLOG_SUBJECTS.append(_backlog_hook)


def _result_view(r: dict[str, Any], session: dict[str, Any], revals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    today = clock.today().isoformat()
    open_reval = bool(session.get("revaluation_until")) and today <= session["revaluation_until"]
    return {
        "id": str(r["_id"]),
        "exam": session["name"],
        "semesters": r.get("semesters", []),
        "sgpa": r["sgpa"],
        "outcome": r["outcome"],
        "credits": r["credits"],
        "credits_earned": r["credits_earned"],
        "revaluation_until": session.get("revaluation_until"),
        "subjects": [
            {
                **{
                    k: s[k]
                    for k in (
                        "code",
                        "name",
                        "credits",
                        "internal",
                        "external",
                        "total",
                        "grade",
                        "grade_point",
                        "passed",
                    )
                },
                "revaluation": (
                    {"status": revals[s["code"]]["status"], "status_label": REVAL_STATUS[revals[s["code"]]["status"]]}
                    if s["code"] in revals
                    else None
                ),
                "can_request_revaluation": open_reval and s["code"] not in revals,
            }
            for s in r["subjects"]
        ],
    }


def my_results(ctx: AuthContext) -> dict[str, Any]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    db = get_db()
    rows = _attempts(student["_id"], published_only=True)
    sessions = {s["_id"]: s for s in db.exam_sessions.find({"_id": {"$in": [r["session_id"] for r in rows]}})}
    revals: dict[ObjectId, dict[str, dict[str, Any]]] = defaultdict(dict)
    for v in db.revaluations.find({"student_id": student["_id"]}):
        revals[v["result_id"]][v["code"]] = v
    st = standing(student["_id"])
    return {
        "cgpa": st["cgpa"],
        "credits_earned": st["credits_earned"],
        "backlogs": [{k: v for k, v in b.items() if k != "subject_id"} for b in st["backlogs"]],
        "results": [_result_view(r, sessions[r["session_id"]], revals[r["_id"]]) for r in reversed(rows)],
    }


def my_result(ctx: AuthContext, result_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    db = get_db()
    r = db.results.find_one({"_id": oid(result_id, "Result")})
    if not r or r["student_id"] != student["_id"]:
        raise AppError(404, "Result not found.")
    session = db.exam_sessions.find_one({"_id": r["session_id"]})
    if not session or not session.get("results_published"):
        raise AppError(404, "Result not found.")
    return r, session, student


# --- revaluation ----------------------------------------------------------------------------


def request_revaluation(ctx: AuthContext, result_id: str, code: str, ip: str) -> dict[str, Any]:
    r, session, student = my_result(ctx, result_id)
    if not session.get("revaluation_until") or clock.today().isoformat() > session["revaluation_until"]:
        raise AppError(409, "The last date for revaluation has passed.", "closed")
    subject = next((s for s in r["subjects"] if s["code"] == code.upper()), None)
    if not subject:
        raise AppError(422, "That paper isn't in this result.", field="code")
    try:
        get_db().revaluations.insert_one(
            {
                "result_id": r["_id"],
                "session_id": session["_id"],
                "student_id": student["_id"],
                "code": subject["code"],
                "old": {k: subject[k] for k in ("external", "total", "grade", "grade_point", "passed")},
                "status": "requested",
                "requested_at": clock.now(),
            }
        )
    except DuplicateKeyError as e:
        raise AppError(409, "You already asked for revaluation of this paper.", "conflict") from e
    audit.record(
        "results.revaluation_requested",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=student["_id"],
        ip=ip,
        details={"code": subject["code"]},
    )
    return my_results(ctx)


def list_revaluations(ctx: AuthContext, status: str | None) -> list[dict[str, Any]]:
    if not ctx.permissions & {P.EXAMS_MANAGE, P.RESULTS_READ}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    db = get_db()
    rows = list(db.revaluations.find({"status": status} if status else {}).sort("requested_at", ASCENDING).limit(500))
    students = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}}, {"name": 1, "prn": 1})
    }
    sessions = {
        s["_id"]: s["name"]
        for s in db.exam_sessions.find({"_id": {"$in": [r["session_id"] for r in rows]}}, {"name": 1})
    }
    return [
        {
            "id": str(r["_id"]),
            "exam": sessions.get(r["session_id"]),
            "name": students.get(r["student_id"], {}).get("name"),
            "prn": students.get(r["student_id"], {}).get("prn"),
            "code": r["code"],
            "old": r["old"],
            "new": r.get("new"),
            "status": r["status"],
            "status_label": REVAL_STATUS[r["status"]],
            "requested_at": r["requested_at"].isoformat(),
        }
        for r in rows
    ]


def decide_revaluation(ctx: AuthContext, reval_id: str, body: dict[str, Any], ip: str) -> dict[str, Any]:
    _require_manage(ctx)
    db = get_db()
    v = db.revaluations.find_one({"_id": oid(reval_id, "Revaluation")})
    if not v:
        raise AppError(404, "Revaluation not found.")
    status = body["status"]
    changes: dict[str, Any] = {"status": status, "decided_by": ctx.user_id, "decided_at": clock.now()}
    if status == "changed":
        grade = (body.get("grade") or "").upper()
        if grade not in GRADE_POINTS and body.get("grade_point") is None:
            raise AppError(422, "Give the new grade.", field="grade")
        new = {
            "external": body.get("external"),
            "total": body.get("total"),
            "grade": grade,
            "grade_point": body.get("grade_point") if body.get("grade_point") is not None else GRADE_POINTS[grade],
            "passed": grade not in FAILED,
        }
        r = db.results.find_one({"_id": v["result_id"]})
        assert r is not None
        updated = {k: x for k, x in new.items() if x is not None}  # unchanged marks stay as they were
        subjects = [{**s, **updated} if s["code"] == v["code"] else s for s in r["subjects"]]
        db.results.update_one(
            {"_id": r["_id"]},
            {
                "$set": {
                    "subjects": subjects,
                    "sgpa": sgpa(subjects),
                    "outcome": outcome(subjects),
                    "credits_earned": sum(s["credits"] for s in subjects if s["passed"]),
                }
            },
        )
        changes["new"] = new
    db.revaluations.update_one({"_id": v["_id"]}, {"$set": changes})
    audit.record(
        f"results.revaluation_{status}",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=v["student_id"],
        ip=ip,
        details={"code": v["code"], **({"new_grade": changes["new"]["grade"]} if "new" in changes else {})},
    )
    return next(x for x in list_revaluations(ctx, None) if x["id"] == reval_id)
