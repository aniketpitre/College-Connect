"""
Data exports (spec §2.3 "Data export", §3.19).

The System Admin asks for a full CSV of students, fee balances or receipts; the Principal
approves; then the person who asked can download it for 24 hours. Every step and every download
is in the audit log. Students download their own data as JSON at any time (/me/data-export).
"""

import csv
import io
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.fees import ledger
from app.modules.fees import receipts as receipts_mod
from app.modules.students import service as students

register_indexes(
    "export_requests",
    [
        IndexModel([("requested_at", DESCENDING)]),
        # One open request per dataset.
        IndexModel([("open_key", ASCENDING)], unique=True, partialFilterExpression={"open_key": {"$type": "string"}}),
    ],
)

DATASETS = {
    "students": "Students (all records)",
    "fees": "Fee balances (per student, per year)",
    "receipts": "Receipts (all)",
    "full": "Everything (all records and files, with a data dictionary; restores into a fresh database)",
}
VALID_FOR = timedelta(hours=24)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as e:
        raise AppError(404, "Request not found.") from e


def _names(ids: list[Any]) -> dict[Any, str]:
    return {u["_id"]: u["name"] for u in get_db().users.find({"_id": {"$in": ids}}, {"name": 1})}


def view(r: dict[str, Any], names: dict[Any, str] | None = None) -> dict[str, Any]:
    names = names if names is not None else _names([r["requested_by"], r.get("decided_by")])
    expires = r.get("expires_at")
    return {
        "id": str(r["_id"]),
        "dataset": r["dataset"],
        "dataset_label": DATASETS[r["dataset"]],
        "reason": r["reason"],
        "status": r["status"],
        "requested_by": names.get(r["requested_by"]),
        "requested_by_id": str(r["requested_by"]),
        "requested_at": r["requested_at"].isoformat(),
        "decided_by": names.get(r.get("decided_by")),
        "decided_at": r["decided_at"].isoformat() if r.get("decided_at") else None,
        "decision_reason": r.get("decision_reason"),
        "expires_at": expires.isoformat() if expires else None,
        "downloadable": r["status"] == "approved" and expires is not None and expires > datetime.now(UTC),
        "downloads": r.get("downloads", 0),
    }


def request_export(ctx: AuthContext, dataset: str, reason: str, ip: str) -> dict[str, Any]:
    if dataset not in DATASETS:
        raise AppError(422, "Choose what to export.", field="dataset")
    if len(reason.strip()) < 5:
        raise AppError(422, "Say why you need this export.", field="reason")
    doc: dict[str, Any] = {
        "dataset": dataset,
        "reason": reason.strip(),
        "status": "pending",
        "requested_by": ctx.user_id,
        "requested_at": datetime.now(UTC),
        "open_key": dataset,
    }
    try:
        doc["_id"] = get_db().export_requests.insert_one(doc).inserted_id
    except DuplicateKeyError as e:
        raise AppError(409, "An export of this data is already waiting for approval.", "conflict") from e
    audit.record(
        "exports.requested",
        actor_id=ctx.user_id,
        target_type="export_request",
        target_id=doc["_id"],
        ip=ip,
        reason=reason,
        details={"dataset": dataset},
    )
    return view(doc)


def list_requests(ctx: AuthContext) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if P.APPROVALS_DECIDE not in ctx.permissions:
        query["requested_by"] = ctx.user_id  # requesters see their own; approvers see all
    rows = list(get_db().export_requests.find(query).sort("requested_at", DESCENDING).limit(200))
    names = _names(list({r["requested_by"] for r in rows} | {r["decided_by"] for r in rows if r.get("decided_by")}))
    return [view(r, names) for r in rows]


def decide(ctx: AuthContext, request_id: str, approve: bool, reason: str | None, ip: str) -> dict[str, Any]:
    db = get_db()
    rid = _oid(request_id)
    pending = db.export_requests.find_one({"_id": rid})
    if not pending:
        raise AppError(404, "Request not found.")
    if pending["requested_by"] == ctx.user_id:
        raise AppError(403, "You can't approve your own request.", "same_person")
    if not approve and not (reason and reason.strip()):
        raise AppError(422, "Give a reason for rejecting.", field="reason")
    now = datetime.now(UTC)
    changes: dict[str, Any] = {
        "status": "approved" if approve else "rejected",
        "decided_by": ctx.user_id,
        "decided_at": now,
        "decision_reason": (reason or "").strip() or None,
    }
    if approve:
        changes["expires_at"] = now + VALID_FOR
    doc = db.export_requests.find_one_and_update(
        {"_id": rid, "status": "pending"}, {"$set": changes, "$unset": {"open_key": ""}}, return_document=True
    )
    if not doc:
        raise AppError(409, "This request was already decided.", "conflict")
    audit.record(
        f"exports.{'approved' if approve else 'rejected'}",
        actor_id=ctx.user_id,
        target_type="export_request",
        target_id=rid,
        ip=ip,
        reason=reason,
        details={"dataset": doc["dataset"]},
    )
    return view(doc)


def approved_request(ctx: AuthContext, request_id: str) -> dict[str, Any]:
    """The asker's own approved, unexpired export request."""
    r = get_db().export_requests.find_one({"_id": _oid(request_id)})
    if not r or r["requested_by"] != ctx.user_id:
        raise AppError(404, "Request not found.")
    if r["status"] != "approved":
        raise AppError(409, "This export hasn't been approved.", "not_approved")
    if r["expires_at"] <= datetime.now(UTC):
        raise AppError(410, "This export has expired. Ask again.", "expired")
    return r


def download(ctx: AuthContext, request_id: str, ip: str) -> tuple[str, bytes]:
    db = get_db()
    r = approved_request(ctx, request_id)
    if r["dataset"] == "full":
        raise AppError(409, "Download the full export from the Data export page.", "use_full_export")
    data = BUILDERS[r["dataset"]]()
    db.export_requests.update_one({"_id": r["_id"]}, {"$inc": {"downloads": 1}})
    audit.record(
        "exports.downloaded",
        actor_id=ctx.user_id,
        target_type="export_request",
        target_id=r["_id"],
        ip=ip,
        details={"dataset": r["dataset"], "bytes": len(data)},
    )
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"collegeconnect-{r['dataset']}-{stamp}.csv", data


# --- CSV builders ----------------------------------------------------------------------------


def _csv(header: list[str], rows: list[list[Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows:
        # A leading = + - @ makes spreadsheets run a formula; prefix it so it stays text.
        writer.writerow(["'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v for v in row])
    return ("﻿" + out.getvalue()).encode("utf-8")  # BOM so Excel reads Devanagari correctly


def _rupees(paise: int) -> str:
    return f"{paise / 100:.2f}"


def students_csv() -> bytes:
    lookups = students._lookups()
    header = [
        "PRN", "Name", "Mother's name", "Gender", "Date of birth", "Programme", "Year", "Division", "Roll no",
        "Category", "Status", "Phone", "Email", "APAAR ID", "Admission date", "Guardian name", "Guardian phone",
        "Address",
    ]  # fmt: skip
    rows = []
    for d in get_db().students.find({}).sort("prn", ASCENDING):
        s = students.summary(d, lookups)
        guardian = d.get("guardian") or {}
        address = d.get("address") or {}
        rows.append(
            [
                s["prn"], s["name"], d.get("mother_name"), d.get("gender"), d.get("dob"), s["programme_code"],
                s["year_label"], s["division"], s["roll_no"], s["category_code"], s["status"], s["phone"],
                s["email"], d.get("apaar_id"), d.get("admission_date"), guardian.get("name"), guardian.get("phone"),
                ", ".join(str(v) for v in address.values() if v) if isinstance(address, dict) else address,
            ]
        )  # fmt: skip
    return _csv(header, rows)


COLUMNS = [
    "demand",
    "charge",
    "opening_due",
    "payment",
    "concession",
    "scholarship",
    "opening_paid",
    "refund",
    "reversal",
]


def fees_csv() -> bytes:
    db = get_db()
    totals: dict[tuple[Any, Any], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in db.ledger_entries.aggregate(
        [
            {
                "$group": {
                    "_id": {"s": "$student_id", "y": "$academic_year_id", "t": "$type"},
                    "amount": {"$sum": "$amount"},
                }
            }
        ]
    ):
        key = row["_id"]
        totals[(key["s"], key["y"])][key["t"]] += row["amount"]
    years = {y["_id"]: y["name"] for y in db.academic_years.find({}, {"name": 1})}
    people = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": list({k[0] for k in totals})}}, {"prn": 1, "name": 1})
    }
    rows = []
    for (sid, yid), t in sorted(
        totals.items(), key=lambda kv: (people.get(kv[0][0], {}).get("prn", ""), years.get(kv[0][1], ""))
    ):
        s = people.get(sid, {})
        rows.append(
            [s.get("prn"), s.get("name"), years.get(yid)]
            + [_rupees(abs(t.get(c, 0)) if c != "reversal" else t.get(c, 0)) for c in COLUMNS]
            + [_rupees(sum(t.values()))]
        )
    header = ["PRN", "Name", "Academic year"] + [ledger.LABELS[c] for c in COLUMNS] + ["Balance"]
    return _csv(header, rows)


def receipts_csv() -> bytes:
    header = [
        "Receipt no", "Date", "PRN", "Name", "Academic year", "Amount", "Mode", "Reference", "Bank", "Status",
        "Cancelled on", "Cancel reason", "Collected by", "Heads",
    ]  # fmt: skip
    rows = []
    for r in get_db().receipts.find({}).sort("collected_at", ASCENDING):
        v = receipts_mod.view(r)
        student = v["student"] or {}
        rows.append(
            [
                v["number"], v["collected_at"][:10], student.get("prn"), student.get("name"), v["academic_year"],
                _rupees(v["amount"]), v["mode_label"], v["reference"], v["bank"], v["status"],
                (v["cancelled_at"] or "")[:10], v["cancel_reason"], v["collected_by"],
                "; ".join(f"{ln['code']} {_rupees(ln['amount'])}" for ln in v["lines"]),
            ]
        )  # fmt: skip
    return _csv(header, rows)


BUILDERS = {"students": students_csv, "fees": fees_csv, "receipts": receipts_csv}


# --- a student's own data --------------------------------------------------------------------


def my_data(ctx: AuthContext, ip: str) -> dict[str, Any]:
    """Everything the college holds about the signed-in student, as JSON (spec §3.19)."""
    student = students.my_student(ctx)
    db = get_db()
    user = ctx.user
    record = students.view(student)
    record["documents"] = [{k: v for k, v in d.items() if k != "url"} for d in record["documents"]]
    record.pop("photo_url", None)
    entries = db.ledger_entries.find({"student_id": student["_id"]}).sort("at", ASCENDING)
    years = {y["_id"]: y["name"] for y in db.academic_years.find({}, {"name": 1})}
    receipts = db.receipts.find({"student_id": student["_id"]}).sort("collected_at", ASCENDING)
    sign_ins = (
        db.audit_log.find(
            {"actor_id": ctx.user_id, "action": {"$in": ["auth.login.succeeded", "auth.login.failed"]}},
            {"at": 1, "action": 1, "ip": 1},
        )
        .sort("at", DESCENDING)
        .limit(200)
    )
    audit.record("exports.my_data", actor_id=ctx.user_id, target_type="student", target_id=student["_id"], ip=ip)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {
            "name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "language": user.get("language"),
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
        },
        "student_record": record,
        "correction_requests": students.my_requests(ctx),
        "consents": students.jsonable(
            [
                {k: v for k, v in c.items() if k not in ("_id", "user_id")}
                for c in db.consents.find({"user_id": ctx.user_id})
            ]
        ),
        "fee_ledger": [
            {
                "date": e["at"].isoformat(),
                "academic_year": years.get(e["academic_year_id"]),
                "type": ledger.LABELS.get(e["type"], e["type"]),
                "amount_rupees": _rupees(e["amount"]),
                "reason": e.get("reason"),
            }
            for e in entries
        ],
        "receipts": [
            {
                k: v
                for k, v in receipts_mod.view(r).items()
                if k
                in {"number", "academic_year", "amount", "mode_label", "reference", "collected_at", "status", "lines"}
            }
            for r in receipts
        ],
        "sign_ins": [
            {
                "at": s["at"].isoformat(),
                "result": "ok" if s["action"].endswith("succeeded") else "failed",
                "ip": s.get("ip"),
            }
            for s in sign_ins
        ],
    }
