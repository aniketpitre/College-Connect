"""
Full data export (spec U12 "no lock-in", plan 4.6).

Everything the college has in CollegeConnect, collection by collection, as MongoDB Extended JSON
(one document per line, so ids, dates and files survive exactly), with a data dictionary. It
goes through the same approval as other exports: the System Admin asks, the Principal approves,
then it can be downloaded for 24 hours. Responses on Vercel are limited to about 4.5 MB, so the
browser fetches each collection in pages and builds the ZIP itself; `scripts.restore_export`
loads that ZIP into a fresh database.

Left out on purpose: sign-in sessions, one-time codes, password-reset links, rate-limit counters,
the outgoing message queue and API keys; and every account's password hash and 2-step secret.
After a restore, people set a new password with "Forgot password".
"""

from collections import Counter
from datetime import datetime
from typing import Any

from bson import ObjectId, json_util
from bson.binary import Binary

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db
from app.core.errors import AppError

EXCLUDED = {"sessions", "login_codes", "password_resets", "rate_limits", "message_queue", "api_keys"}
STRIPPED = {"users": ("password_hash", "mfa")}
PAGE_BYTES = 2_500_000
PAGE_DOCS = 1000
JSON_OPTIONS = json_util.CANONICAL_JSON_OPTIONS

DESCRIPTIONS = {
    "academic_years": "Academic years (June–May); one is marked current.",
    "departments": "Departments of the college.",
    "programmes": "Programmes (e.g. BCA) with duration and year labels.",
    "divisions": "Classes: programme, year of study and division name.",
    "subjects": "Subjects per programme and semester, with credits and maximum marks.",
    "categories": "Admission / reservation categories (OPEN, OBC, SC, …).",
    "users": "Sign-in accounts of staff, students, parents and applicants (no passwords in this export).",
    "students": "Student records: personal, academic and contact details, documents, mentor.",
    "ledger_entries": (
        "Each student's fee account: demands, charges, payments, concessions, scholarships, reversals (paise)."
    ),
    "receipts": "Fee receipts with gap-free numbers (paise).",
    "fee_heads": "Fee heads (tuition, development, …).",
    "fee_structures": "Fee structures per programme, year and category, with installments.",
    "scholarships": "Scholarships expected, sanctioned and received per student and year.",
    "approvals": "Requests waiting for or decided by the Principal (concessions, cancellations, refunds).",
    "timetables": "Timetables per class and term.",
    "timetable_slots": "Weekly lectures: day, time, subject, teacher, room.",
    "timetable_changes": "One-day changes: cancellations and substitutes.",
    "attendance_sessions": "One record per lecture held: who was absent.",
    "assessment_schemes": "Internal assessment components per subject.",
    "marks_sheets": "Internal marks per class and subject, with their approval workflow.",
    "exam_sessions": "University / college exam sessions.",
    "exam_forms": "Exam forms and seat numbers.",
    "results": "Results per student and exam session, subject-wise grades and SGPA.",
    "certificate_requests": "Certificate requests and their status.",
    "certificates": "Issued certificates with numbers and verify codes.",
    "notices": "Notices with audience, schedule and translations.",
    "audit_log": "Who did what and when (every change of record).",
    "files": "Uploaded files (photos, documents, evidence) as binary data.",
    "admission_cycles": "Admission cycles: seats, reserved seats, dates.",
    "applications": "Admission applications and their scrutiny.",
    "books": "Library catalogue (titles).",
    "book_copies": "Library copies with barcodes.",
    "loans": "Library issues and returns.",
    "hostel_allotments": "Hostel bed allotments.",
    "drives": "Placement drives.",
    "drive_registrations": "Students registered for placement drives and their rounds.",
    "grievances": "Grievances with their history (anonymous ones carry no visible name).",
    "staff_profiles": "Staff records and qualifications.",
    "leave_requests": "Staff leave requests and decisions.",
    "risk_flags": "Early-warning levels and reasons per student (confidential).",
    "mentor_notes": "Counselling notes (confidential).",
    "naac_evidence": "Evidence files linked to NAAC metrics.",
    "settings": "College settings (institution details, rules, thresholds).",
}


def collections() -> list[str]:
    return sorted(c for c in get_db().list_collection_names() if c not in EXCLUDED and not c.startswith("system."))


def _kind(value: Any) -> str:
    if isinstance(value, ObjectId):
        return "id"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, datetime):
        return "date-time"
    if isinstance(value, bytes | Binary):
        return "binary"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "text"


def dictionary() -> list[dict[str, Any]]:
    """Each collection with its document count, what it holds and its fields (from a sample)."""
    db = get_db()
    out = []
    for name in collections():
        fields: dict[str, Counter[str]] = {}
        for doc in db[name].find({}).limit(50):
            for k, v in doc.items():
                if k in STRIPPED.get(name, ()):
                    continue
                fields.setdefault(k, Counter())[_kind(v)] += 1
        out.append(
            {
                "collection": name,
                "count": db[name].estimated_document_count(),
                "description": DESCRIPTIONS.get(name, ""),
                "fields": [{"name": k, "types": sorted(c)} for k, c in sorted(fields.items())],
            }
        )
    return out


def dictionary_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CollegeConnect data dictionary",
        "",
        "Each collection is a file `collections/<name>.jsonl`: one MongoDB Extended JSON (canonical) "
        "document per line.",
        "Money is in paise (100 paise = Rs. 1). Ids are ObjectIds and link records across collections.",
        "Passwords, 2-step secrets, sessions, one-time codes and API keys are not included.",
        "",
    ]
    for r in rows:
        lines += [f"## {r['collection']} ({r['count']} records)", "", r["description"] or "", ""]
        lines += [f"- `{f['name']}`: {', '.join(f['types'])}" for f in r["fields"]]
        lines.append("")
    return "\n".join(lines)


def manifest(ctx: AuthContext, request: dict[str, Any], ip: str) -> dict[str, Any]:
    rows = dictionary()
    audit.record(
        "exports.full_started",
        actor_id=ctx.user_id,
        target_type="export_request",
        target_id=request["_id"],
        ip=ip,
        details={"collections": len(rows)},
    )
    return {"collections": rows, "dictionary_md": dictionary_markdown(rows)}


def page(collection: str, after: str | None) -> tuple[str, str | None]:
    """Up to ~2.5 MB of one collection as JSON lines, and the id to continue after (None at the end)."""
    if collection not in collections():
        raise AppError(404, "No such collection in the export.")
    query: dict[str, Any] = {}
    if after:
        query["_id"] = {"$gt": json_util.loads(after)}
    strip = STRIPPED.get(collection, ())
    lines: list[str] = []
    size, last = 0, None
    for doc in get_db()[collection].find(query).sort("_id", 1).limit(PAGE_DOCS):
        for k in strip:
            doc.pop(k, None)
        line = json_util.dumps(doc, json_options=JSON_OPTIONS)
        if lines and size + len(line) > PAGE_BYTES:
            return "\n".join(lines) + "\n", json_util.dumps(last, json_options=JSON_OPTIONS)
        lines.append(line)
        size += len(line) + 1
        last = doc["_id"]
    more = len(lines) == PAGE_DOCS
    body = "\n".join(lines) + ("\n" if lines else "")
    return body, json_util.dumps(last, json_options=JSON_OPTIONS) if more and last is not None else None
