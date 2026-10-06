"""
Scholarship eligibility checker (spec U11, plan 4.5).

Each scholarship scheme is a set of simple rules (category, family income limit, state of
domicile, minimum attendance, previous exam percentage, gender, year of study) and the documents
its portal asks for. Each student sees which schemes they may qualify for, the rule they don't
meet, what information is missing, and which documents to upload first. It is a guide, not a
decision: the portal (MahaDBT, NSP) decides, and the scheme rules are settings the Accounts office
keeps up to date. The family income is the student's own declaration, used only for this guide.

The defaults are common Maharashtra/central schemes for undergraduates; their limits change
from year to year, so the office should check them against the portal each year.
"""

from typing import Any

from pymongo import ASCENDING, IndexModel

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.modules.attendance import stats
from app.modules.eligibility.schemas import IncomeIn, SchemeIn
from app.modules.setup import service as setup
from app.modules.students import service as students

register_indexes("scholarship_schemes", [IndexModel([("code", ASCENDING)], unique=True)])

_COMMON = ["income_certificate", "domicile_certificate", "hsc_marksheet", "aadhaar_masked"]
DEFAULT_SCHEMES: list[dict[str, Any]] = [
    {
        "code": "postmatric-sc",
        "name": "Government of India Post-Matric Scholarship (SC)",
        "portal": "MahaDBT",
        "categories": ["SC"],
        "income_limit": 250_000,
        "domicile": "Maharashtra",
        "documents": ["caste_certificate", *_COMMON],
    },
    {
        "code": "postmatric-st",
        "name": "Post-Matric Scholarship for Scheduled Tribe students",
        "portal": "MahaDBT",
        "categories": ["ST"],
        "income_limit": 250_000,
        "domicile": "Maharashtra",
        "documents": ["caste_certificate", *_COMMON],
    },
    {
        "code": "postmatric-obc",
        "name": "Post-Matric Scholarship for OBC students",
        "portal": "MahaDBT",
        "categories": ["OBC"],
        "income_limit": 150_000,
        "domicile": "Maharashtra",
        "documents": ["caste_certificate", *_COMMON],
    },
    {
        "code": "postmatric-vjnt-sbc",
        "name": "Post-Matric Scholarship for VJNT and SBC students",
        "portal": "MahaDBT",
        "categories": ["VJ-NT", "SBC"],
        "income_limit": 150_000,
        "domicile": "Maharashtra",
        "documents": ["caste_certificate", *_COMMON],
    },
    {
        "code": "ebc-shahu-maharaj",
        "name": "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti (EBC)",
        "portal": "MahaDBT",
        "categories": ["OPEN", "EWS", "SEBC"],
        "income_limit": 800_000,
        "domicile": "Maharashtra",
        "documents": _COMMON,
    },
    {
        "code": "central-sector",
        "name": "Central Sector Scheme of Scholarship for College Students",
        "portal": "NSP",
        "categories": [],
        "income_limit": 450_000,
        "min_previous_percentage": 80,
        "years": [1],
        "documents": ["hsc_marksheet", "income_certificate", "aadhaar_masked"],
        "note": "For students above the 80th percentile of their Class 12 board; the 80% here is a rough guide.",
    },
]


def _defaults() -> None:
    db = get_db()
    if db.scholarship_schemes.count_documents({}) == 0:
        db.scholarship_schemes.insert_many([SchemeIn(**s).model_dump() for s in DEFAULT_SCHEMES])


def schemes(active_only: bool = False) -> list[dict[str, Any]]:
    _defaults()
    query = {"active": True} if active_only else {}
    return [
        {k: v for k, v in s.items() if k != "_id"}
        for s in get_db().scholarship_schemes.find(query).sort("name", ASCENDING)
    ]


def save_scheme(ctx: AuthContext, body: SchemeIn, *, create: bool) -> dict[str, Any]:
    _defaults()
    db = get_db()
    data = body.model_dump()
    data["categories"] = [c.strip().upper() for c in data["categories"] if c.strip()]
    if create:
        if db.scholarship_schemes.find_one({"code": body.code}):
            raise AppError(409, "A scheme with this code exists.", "conflict", "code")
        db.scholarship_schemes.insert_one(data)
    elif not db.scholarship_schemes.find_one_and_replace({"code": body.code}, data):
        raise AppError(404, "Scheme not found.")
    audit.record("scholarship_scheme.saved", actor_id=ctx.user_id, details={"code": body.code, "created": create})
    return {k: v for k, v in data.items() if k != "_id"}


# --- checking a student ---------------------------------------------------------------------


def _facts(student: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    category = (
        db.categories.find_one({"_id": student.get("category_id")}, {"code": 1}) if student.get("category_id") else None
    )
    flag = db.risk_flags.find_one({"_id": student["_id"]}, {"signals": 1})
    attendance = (flag or {}).get("signals", {}).get("attendance")
    if attendance is None:
        attendance = stats.student_summary(student)["overall"]["percent"]
    docs = {d["type"] for d in student.get("documents", []) if d.get("status") in {"verified", "pending"}}
    return {
        "category": category["code"] if category else None,
        "income": student.get("family_income"),
        "state": (student.get("address") or {}).get("state") or None,
        "attendance": attendance,
        "percentage": (student.get("previous_education") or {}).get("percentage"),
        "gender": student.get("gender"),
        "year": student.get("year_of_study"),
        "documents": docs,
    }


def check(scheme: dict[str, Any], f: dict[str, Any], applied: dict[str, str]) -> dict[str, Any]:
    """One scheme for one student: status, the rules not met (with their limits), what is unknown."""
    failed: list[dict[str, Any]] = []
    unknown: list[str] = []

    def rule(key: str, value: Any, ok: bool | None, **params: Any) -> None:
        if value is None or ok is None:
            unknown.append(key)
        elif not ok:
            failed.append({"rule": key, **params})

    if scheme["categories"]:
        rule("category", f["category"], f["category"] in scheme["categories"], allowed=scheme["categories"])
    if scheme.get("income_limit") is not None:
        rule(
            "income",
            f["income"],
            f["income"] is not None and f["income"] <= scheme["income_limit"],
            limit=scheme["income_limit"],
        )
    if scheme.get("domicile"):
        state = f["state"]
        rule(
            "domicile",
            state,
            state is not None and state.strip().lower() == scheme["domicile"].lower(),
            state=scheme["domicile"],
        )
    if scheme.get("min_attendance") is not None and f["attendance"] is not None:
        rule(
            "attendance", f["attendance"], f["attendance"] >= scheme["min_attendance"], minimum=scheme["min_attendance"]
        )
    if scheme.get("min_previous_percentage") is not None:
        pct = f["percentage"]
        rule(
            "percentage",
            pct,
            pct is not None and pct >= scheme["min_previous_percentage"],
            minimum=scheme["min_previous_percentage"],
        )
    if scheme.get("gender") == "female":
        rule("gender", f["gender"], f["gender"] == "female")
    if scheme.get("years"):
        rule("year", f["year"], f["year"] in scheme["years"], years=scheme["years"])
    missing = [d for d in scheme["documents"] if d not in f["documents"]]
    if scheme["name"].lower() in applied:
        status = "applied"
    elif failed:
        status = "not_eligible"
    elif unknown:
        status = "check"
    elif missing:
        status = "missing_documents"
    else:
        status = "likely"
    return {
        "code": scheme["code"],
        "name": scheme["name"],
        "portal": scheme["portal"],
        "link": scheme.get("link"),
        "note": scheme.get("note"),
        "status": status,
        "application_status": applied.get(scheme["name"].lower()),
        "failed": failed,
        "unknown": unknown,
        "missing_documents": missing,
    }


def _applied(student_id: Any) -> dict[str, str]:
    year = setup.current_year()
    if not year:
        return {}
    return {
        s["scheme"].lower(): s["status"]
        for s in get_db().scholarships.find(
            {"student_id": student_id, "academic_year_id": year["_id"]}, {"scheme": 1, "status": 1}
        )
    }


ORDER = {"likely": 0, "missing_documents": 1, "check": 2, "applied": 3, "not_eligible": 4}


def for_student(student: dict[str, Any]) -> dict[str, Any]:
    f = _facts(student)
    applied = _applied(student["_id"])
    rows = [check(s, f, applied) for s in schemes(active_only=True)]
    rows.sort(key=lambda r: (ORDER[r["status"]], r["name"]))
    return {
        "family_income": f["income"],
        "income_declared_at": student.get("income_declared_at"),
        "facts": {k: v for k, v in f.items() if k != "documents"},
        "schemes": rows,
    }


def mine(ctx: AuthContext) -> dict[str, Any]:
    return for_student(students.my_student(ctx))


def declare_income(ctx: AuthContext, body: IncomeIn) -> dict[str, Any]:
    if ctx.user.get("kind") != "student":
        raise AppError(403, "This is for students.", "forbidden")
    student = students.my_student(ctx)
    get_db().students.update_one(
        {"_id": student["_id"]}, {"$set": {"family_income": body.family_income, "income_declared_at": clock.now()}}
    )
    audit.record("student.income_declared", actor_id=ctx.user_id, target_type="student", target_id=student["_id"])
    return mine(ctx)


def candidates(code: str) -> dict[str, Any]:
    """Accounts: students who may qualify for a scheme and haven't applied yet this year."""
    scheme = next((s for s in schemes() if s["code"] == code), None)
    if not scheme:
        raise AppError(404, "Scheme not found.")
    db = get_db()
    query: dict[str, Any] = {"status": "active"}
    if scheme["categories"]:
        cats = [c["_id"] for c in db.categories.find({"code": {"$in": scheme["categories"]}}, {"_id": 1})]
        query["category_id"] = {"$in": cats}
    rows = []
    for s in db.students.find(query).sort("prn", ASCENDING).limit(1000):
        r = check(scheme, _facts(s), _applied(s["_id"]))
        if r["status"] in {"likely", "missing_documents", "check"}:
            rows.append(
                {
                    "student_id": str(s["_id"]),
                    "name": s["name"],
                    "prn": s.get("prn"),
                    "status": r["status"],
                    "unknown": r["unknown"],
                    "missing_documents": r["missing_documents"],
                }
            )
    rows.sort(key=lambda r: (ORDER[r["status"]], r["prn"] or ""))
    return {"scheme": scheme, "students": rows}
