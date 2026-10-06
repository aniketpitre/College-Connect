"""
The open REST API (`/api/v1/open/*`): read-only, for other systems, authenticated with API keys
and limited to each key's scopes. Its own OpenAPI document and docs page are published at
`/api/v1/open/openapi.json` and `/api/v1/open/docs`.
"""

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from pymongo import ASCENDING

from app.core.auth import AuthContext, require
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.attendance import stats
from app.modules.fees import ledger
from app.modules.integrations import keys
from app.modules.integrations.keys import KeyIn, require_scope

router = APIRouter(tags=["api keys"])
open_router = APIRouter(prefix="/open", tags=["open API"])
MANAGE = Depends(require(P.API_KEYS_MANAGE))
LIMIT = Query(100, ge=1, le=500)
AFTER = Query(None, description="Continue after this id (the `next_after` of the previous page)")
SCOPE_SETUP = Depends(require_scope("setup:read"))
SCOPE_STUDENTS = Depends(require_scope("students:read"))
SCOPE_FEES = Depends(require_scope("fees:read"))
SCOPE_ATTENDANCE = Depends(require_scope("attendance:read"))
SCOPE_RESULTS = Depends(require_scope("results:read"))
SCOPE_TIMETABLE = Depends(require_scope("timetable:read"))
SCOPE_NOTICES = Depends(require_scope("notices:read"))


@router.get("/api-keys")
def list_keys(ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return keys.list_keys()


@router.post("/api-keys", status_code=201)
def create_key(body: KeyIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return keys.create(ctx, body, client_ip(request))


@router.post("/api-keys/{key_id}/revoke")
def revoke_key(key_id: str, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return keys.revoke(ctx, key_id, client_ip(request))


# --- the open API ---------------------------------------------------------------------------


def _oid(value: str | None, what: str) -> ObjectId | None:
    if value is None:
        return None
    try:
        return ObjectId(value)
    except Exception as e:  # noqa: BLE001
        raise AppError(422, f"{what} is not a valid id.", field=what.lower().replace(" ", "_")) from e


def _page(
    collection: str,
    query: dict[str, Any],
    limit: int,
    after: str | None,
    shape: Any,
    fields: dict[str, int] | None = None,
) -> dict[str, Any]:
    if after:
        query = {**query, "_id": {"$gt": _oid(after, "after")}}
    rows = list(get_db()[collection].find(query, fields).sort("_id", ASCENDING).limit(limit))
    return {"data": [shape(r) for r in rows], "next_after": str(rows[-1]["_id"]) if len(rows) == limit else None}


def _s(v: Any) -> Any:
    return str(v) if isinstance(v, ObjectId) else v


@open_router.get("/setup", summary="College structure")
def setup(key: dict[str, Any] = SCOPE_SETUP) -> dict[str, Any]:
    db = get_db()

    def plain(rows: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        return [{"id": str(r["_id"]), **{f: _s(r.get(f)) for f in fields}} for r in rows]

    return {
        "academic_years": plain(db.academic_years.find({}), ("name", "start_date", "end_date", "is_current")),
        "departments": plain(db.departments.find({}), ("code", "name", "status")),
        "programmes": plain(
            db.programmes.find({}), ("code", "name", "level", "duration_years", "department_id", "status")
        ),
        "divisions": plain(db.divisions.find({}), ("programme_id", "year_of_study", "name", "status")),
        "subjects": plain(
            db.subjects.find({}), ("programme_id", "semester", "code", "name", "credits", "type", "status")
        ),
    }


@open_router.get("/students", summary="Students (paged)")
def students(
    status: str | None = Query(None, pattern="^(active|tc|graduated|dropped|detained|cancelled)$"),
    division_id: str | None = None,
    limit: int = LIMIT,
    after: str | None = AFTER,
    key: dict[str, Any] = SCOPE_STUDENTS,
) -> dict[str, Any]:
    cats = {c["_id"]: c["code"] for c in get_db().categories.find({}, {"code": 1})}
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if division_id:
        query["division_id"] = _oid(division_id, "Division id")
    fields = {
        k: 1
        for k in (
            "prn",
            "name",
            "programme_id",
            "year_of_study",
            "division_id",
            "status",
            "gender",
            "category_id",
            "email",
            "apaar_id",
            "admission_date",
        )
    }

    def shape(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(s["_id"]),
            **{
                k: _s(s.get(k))
                for k in (
                    "prn",
                    "name",
                    "programme_id",
                    "year_of_study",
                    "division_id",
                    "status",
                    "gender",
                    "email",
                    "apaar_id",
                    "admission_date",
                )
            },
            "category": cats.get(s.get("category_id")),
        }

    return _page("students", query, limit, after, shape, fields)


@open_router.get("/fees/balances", summary="Fee balance per student for a year (paise)")
def fee_balances(
    academic_year_id: str,
    limit: int = LIMIT,
    after: str | None = AFTER,
    key: dict[str, Any] = SCOPE_FEES,
) -> dict[str, Any]:
    year = _oid(academic_year_id, "Academic year id")
    db = get_db()

    def shape(s: dict[str, Any]) -> dict[str, Any]:
        info = ledger.summary(ledger.entries(s["_id"], year))
        return {
            "student_id": str(s["_id"]),
            "prn": s.get("prn"),
            **{k: info[k] for k in ("demand", "paid", "concessions", "scholarships", "balance", "overdue")},
        }

    ids = db.ledger_entries.distinct("student_id", {"academic_year_id": year})
    return _page("students", {"_id": {"$in": ids}}, limit, after, shape, {"prn": 1})


@open_router.get("/attendance", summary="Attendance per student and subject for a class")
def attendance(division_id: str, key: dict[str, Any] = SCOPE_ATTENDANCE) -> dict[str, Any]:
    db = get_db()
    div = _oid(division_id, "Division id")
    people = {s["_id"]: s for s in db.students.find({"division_id": div, "status": "active"}, {"prn": 1})}
    subjects = {s["_id"]: s["code"] for s in db.subjects.find({}, {"code": 1})}
    year = db.academic_years.find_one({"is_current": True}, {"_id": 1})
    rows = stats.tally(list(people), {"division_id": div, **({"academic_year_id": year["_id"]} if year else {})})
    return {
        "data": [
            {
                "student_id": str(sid),
                "prn": people[sid].get("prn"),
                "subject": subjects.get(sub),
                "held": r["held"],
                "attended": r["attended"],
                "percent": round(100 * r["attended"] / r["held"], 1) if r["held"] else None,
            }
            for sid, subs in rows.items()
            for sub, r in subs.items()
        ]
    }


@open_router.get("/results", summary="Published results of an exam session (paged)")
def results(
    session_id: str,
    limit: int = LIMIT,
    after: str | None = AFTER,
    key: dict[str, Any] = SCOPE_RESULTS,
) -> dict[str, Any]:
    db = get_db()
    session = db.exam_sessions.find_one({"_id": _oid(session_id, "Session id"), "results_published": True}, {"name": 1})
    if not session:
        raise AppError(404, "No published results for this session.")
    prns = {}

    def shape(r: dict[str, Any]) -> dict[str, Any]:
        if r["student_id"] not in prns:
            s = db.students.find_one({"_id": r["student_id"]}, {"prn": 1}) or {}
            prns[r["student_id"]] = s.get("prn")
        return {
            "student_id": str(r["student_id"]),
            "prn": prns[r["student_id"]],
            "sgpa": r.get("sgpa"),
            "outcome": r.get("outcome"),
            "subjects": [
                {k: _s(x.get(k)) for k in ("code", "semester", "credits", "grade", "grade_point", "passed")}
                for x in r.get("subjects", [])
            ],
        }

    return _page("results", {"session_id": session["_id"]}, limit, after, shape)


@open_router.get("/timetable", summary="Weekly timetable of a class")
def timetable(division_id: str, key: dict[str, Any] = SCOPE_TIMETABLE) -> dict[str, Any]:
    rows = (
        get_db()
        .timetable_slots.find({"division_id": _oid(division_id, "Division id"), "status": "active"})
        .sort([("day", 1), ("start", 1)])
    )
    return {
        "data": [
            {k: _s(s.get(k)) for k in ("day", "start", "end", "subject_id", "room", "batch", "valid_from", "valid_to")}
            | {"faculty_ids": [str(f) for f in s.get("faculty_ids", [])]}
            for s in rows
        ]
    }


@open_router.get("/notices", summary="Published notices for everyone (latest first)")
def notices(limit: int = LIMIT, key: dict[str, Any] = SCOPE_NOTICES) -> dict[str, Any]:
    rows = (
        get_db().notices.find({"status": "published", "audience.kind": "everyone"}).sort("publish_at", -1).limit(limit)
    )
    return {
        "data": [
            {
                "id": str(n["_id"]),
                "title": n["title"],
                "body": n.get("body", ""),
                "publish_at": n["publish_at"],
                "expires_on": n.get("expires_on"),
            }
            for n in rows
        ]
    }


def open_openapi() -> dict[str, Any]:
    """The open API on its own (paths relative to /api/v1), for other systems' developers."""
    spec = get_openapi(
        title="CollegeConnect open API",
        version="1.0",
        description=(
            "Read-only access to the college's own data for other systems. Ask the Principal for an API key; "
            "send it as `Authorization: Bearer cc_…`. Each key carries scopes: "
            + "; ".join(f"`{k}` ({v})" for k, v in keys.SCOPES.items())
            + f". Lists are paged with `limit` and `after`. Limit: {keys.PER_HOUR} calls an hour per key."
        ),
        routes=open_router.routes,
        servers=[{"url": "/api/v1"}],
    )
    spec.setdefault("components", {})["securitySchemes"] = {"apiKey": {"type": "http", "scheme": "bearer"}}
    spec["security"] = [{"apiKey": []}]
    return spec


@open_router.get("/openapi.json", include_in_schema=False)
def openapi_json() -> dict[str, Any]:
    return open_openapi()


@open_router.get("/docs", include_in_schema=False)
def docs() -> HTMLResponse:
    return get_swagger_ui_html(openapi_url="/api/v1/open/openapi.json", title="CollegeConnect open API")
