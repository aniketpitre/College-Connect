"""
Bulk import of students from Excel (.xlsx) or CSV (spec §3.3, plan item 1.6).

1. validate: the file is parsed and every row checked (same rules as adding one student, plus
   duplicates inside the file and against existing records). Nothing is created; the office gets
   a row-by-row report.
2. commit: only for a file with no errors. Rows are created in chunks (one transaction each) so
   no request runs long on Vercel; each call returns the chunk's temporary passwords, which are
   never stored.
"""

import csv
import io
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from pymongo import ASCENDING, IndexModel

from app.core import audit
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.security import hash_password, temporary_password
from app.modules.students import service
from app.modules.students.schemas import StudentCreate
from app.modules.users import repo as users_repo

register_indexes(
    "imports",
    [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0), IndexModel([("created_by", ASCENDING)])],
)

MAX_ROWS = 2000
MAX_FILE_BYTES = 2 * 1024 * 1024
CHUNK = 50
KEEP_FOR = timedelta(days=1)

# Template columns, in order. "*" marks required ones in the template header comment.
COLUMNS = [
    "prn",
    "name",
    "programme",
    "year",
    "division",
    "roll_no",
    "gender",
    "dob",
    "category",
    "phone",
    "email",
    "mother_name",
    "aadhaar",
    "apaar_id",
    "guardian_name",
    "guardian_relation",
    "guardian_phone",
    "address",
    "city",
    "district",
    "state",
    "pincode",
    "admission_date",
    "previous_exam",
    "previous_board",
    "previous_year",
    "previous_percentage",
]
REQUIRED = ("prn", "name", "programme", "year")
ALIASES = {
    "full_name": "name",
    "student_name": "name",
    "mobile": "phone",
    "mobile_no": "phone",
    "phone_no": "phone",
    "email_id": "email",
    "date_of_birth": "dob",
    "birth_date": "dob",
    "roll": "roll_no",
    "roll_number": "roll_no",
    "programme_code": "programme",
    "program": "programme",
    "course": "programme",
    "year_of_study": "year",
    "class": "year",
    "div": "division",
    "caste_category": "category",
    "aadhar": "aadhaar",
    "aadhaar_no": "aadhaar",
    "abc_id": "apaar_id",
    "apaar": "apaar_id",
    "pin": "pincode",
    "pin_code": "pincode",
    "mother": "mother_name",
    "father_name": "guardian_name",
    "parent_name": "guardian_name",
    "parent_phone": "guardian_phone",
    "guardian_mobile": "guardian_phone",
}
GENDERS = {"m": "male", "male": "male", "f": "female", "female": "female", "o": "other", "other": "other"}
EXAMPLE = {
    "prn": "2026BCA001",
    "name": "Rohan Suresh Patil",
    "programme": "BCA",
    "year": "FY",
    "division": "A",
    "roll_no": "1",
    "gender": "M",
    "dob": "12-04-2007",
    "category": "OPEN",
    "phone": "9876543210",
    "email": "",
    "mother_name": "Sunita",
    "aadhaar": "",
    "apaar_id": "",
    "guardian_name": "Suresh Patil",
    "guardian_relation": "Father",
    "guardian_phone": "9822012345",
    "address": "12 MG Road",
    "city": "Pune",
    "district": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "admission_date": "",
    "previous_exam": "HSC",
    "previous_board": "Maharashtra State Board",
    "previous_year": "2026",
    "previous_percentage": "78.5",
}


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow(EXAMPLE)
    return out.getvalue()


def _key(header: Any) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", str(header or "").strip().lower().replace("*", "")).strip("_")
    return ALIASES.get(k, k)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 9876543210 as 9876543210.0
    return str(value).strip()


def read_rows(filename: str, data: bytes) -> list[dict[str, str]]:
    if not data:
        raise AppError(422, "The file is empty.", field="file")
    if len(data) > MAX_FILE_BYTES:
        raise AppError(413, "The file is too large (2 MB at most).", "file_too_large", "file")
    if data.startswith(b"PK"):
        from openpyxl import load_workbook

        try:
            sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        except Exception as e:  # noqa: BLE001 - any parse failure means "not a usable workbook"
            raise AppError(422, "Could not read this Excel file.", field="file") from e
        values = [[_cell(c) for c in row] for row in sheet.iter_rows(values_only=True)]
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
        values = [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]
    values = [row for row in values if any(row)]
    if not values:
        raise AppError(422, "The file has no rows.", field="file")
    headers = [_key(h) for h in values[0]]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise AppError(422, f"Missing column(s): {', '.join(missing)}. Use the template.", field="file")
    rows = [{h: (row[i] if i < len(row) else "") for i, h in enumerate(headers) if h} for row in values[1:]]
    if len(rows) > MAX_ROWS:
        raise AppError(422, f"At most {MAX_ROWS} students per file.", field="file")
    return rows


def _date(value: str) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Use a date like 12-04-2007.")


class _Lookups:
    def __init__(self) -> None:
        db = get_db()
        active = {"status": "active"}
        self.programmes = {p["code"]: p for p in db.programmes.find(active)}
        self.divisions = {(d["programme_id"], d["year_of_study"], d["name"]): d for d in db.divisions.find(active)}
        self.categories = {c["code"]: c for c in db.categories.find(active)}


def _to_body(row: dict[str, str], lk: _Lookups) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Spreadsheet row → StudentCreate fields, plus problems found while mapping codes to records."""
    problems: list[tuple[str, str]] = []
    body: dict[str, Any] = {"prn": row.get("prn", ""), "name": row.get("name", "")}
    programme = lk.programmes.get(row.get("programme", "").upper())
    if not programme:
        problems.append(("programme", f"Unknown programme '{row.get('programme', '')}'."))
    year_raw = row.get("year", "").upper()
    year: int | None = None
    if programme:
        labels = programme["year_labels"]
        if year_raw in labels:
            year = labels.index(year_raw) + 1
        elif year_raw.isdigit() and 1 <= int(year_raw) <= len(labels):
            year = int(year_raw)
        else:
            problems.append(("year", f"Year must be one of {', '.join(labels)}."))
        body["programme_id"] = str(programme["_id"])
    body["year_of_study"] = year or 1
    if row.get("division") and programme and year:
        division = lk.divisions.get((programme["_id"], year, row["division"].upper()))
        if not division:
            problems.append(("division", f"No division {row['division'].upper()} in {programme['code']} {year_raw}."))
        else:
            body["division_id"] = str(division["_id"])
    if row.get("category"):
        category = lk.categories.get(row["category"].upper())
        if not category:
            problems.append(("category", f"Unknown category '{row['category']}'."))
        else:
            body["category_id"] = str(category["_id"])
    if row.get("gender"):
        gender = GENDERS.get(row["gender"].strip().lower())
        if not gender:
            problems.append(("gender", "Use M, F or O."))
        body["gender"] = gender
    for column, field in (("dob", "dob"), ("admission_date", "admission_date")):
        try:
            body[field] = _date(row.get(column, ""))
        except ValueError as e:
            problems.append((column, str(e)))
    for field in ("roll_no", "phone", "email", "mother_name", "aadhaar", "apaar_id"):
        if row.get(field):
            body[field] = row[field]
    if any(row.get(k) for k in ("guardian_name", "guardian_relation", "guardian_phone")):
        body["guardian"] = {
            "name": row.get("guardian_name", ""),
            "relation": row.get("guardian_relation", ""),
            "phone": row.get("guardian_phone") or None,
        }
    if any(row.get(k) for k in ("address", "city", "district", "pincode")):
        body["address"] = {
            "line": row.get("address", ""),
            "city": row.get("city", ""),
            "district": row.get("district", ""),
            "state": row.get("state") or "Maharashtra",
            "pincode": row.get("pincode", ""),
        }
    if any(row.get(k) for k in ("previous_exam", "previous_board", "previous_year", "previous_percentage")):
        body["previous_education"] = {
            "exam": row.get("previous_exam", ""),
            "board": row.get("previous_board", ""),
            "year": row.get("previous_year") or None,
            "percentage": row.get("previous_percentage") or None,
        }
    return {k: v for k, v in body.items() if v is not None}, problems


def _validation_messages(e: ValidationError) -> list[tuple[str, str]]:
    found = []
    for err in e.errors():
        loc = [str(p) for p in err.get("loc", [])]
        message = err.get("msg", "Invalid value").removeprefix("Value error, ")
        found.append((".".join(loc) or "row", message))
    return found


def validate(ctx: AuthContext, filename: str, data: bytes) -> dict[str, Any]:
    rows = read_rows(filename, data)
    lk = _Lookups()
    db = get_db()
    errors: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    seen: dict[str, dict[str, int]] = {"prn": {}, "email": {}}
    for index, row in enumerate(rows):
        line = index + 2  # spreadsheet row number (row 1 is the header)
        body, problems = _to_body(row, lk)
        try:
            model = StudentCreate.model_validate(body)
        except ValidationError as e:
            problems += _validation_messages(e)
            model = None
        prn = (row.get("prn") or "").strip().upper()
        email = (row.get("email") or "").strip().lower()
        for field, value in (("prn", prn), ("email", email)):
            if value and value in seen[field]:
                problems.append(
                    (field, f"Same {field.upper() if field == 'prn' else field} as row {seen[field][value]}.")
                )
            elif value:
                seen[field][value] = line
        for problem_field, message in problems:
            errors.append({"row": line, "field": problem_field, "message": message, "prn": prn or None})
        if model and not problems:
            valid.append({"line": line, **model.model_dump(mode="json", exclude_none=True)})

    # Already in the database?
    prns = [v["prn"] for v in valid]
    taken_prn = {d["prn"] for d in db.users.find({"prn": {"$in": prns}}, {"prn": 1})}
    emails = [v["email"].lower() for v in valid if v.get("email")]
    taken_email = {d["email"] for d in db.users.find({"email": {"$in": emails}}, {"email": 1})}
    clean = []
    for v in valid:
        if v["prn"] in taken_prn:
            errors.append(
                {
                    "row": v["line"],
                    "field": "prn",
                    "message": "A student with this PRN already exists.",
                    "prn": v["prn"],
                }
            )
        elif v.get("email") and v["email"].lower() in taken_email:
            errors.append(
                {
                    "row": v["line"],
                    "field": "email",
                    "message": "Another account already uses this email.",
                    "prn": v["prn"],
                }
            )
        else:
            clean.append(v)
    errors.sort(key=lambda e: (e["row"], e["field"]))

    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        "filename": filename[:120],
        "status": "validated" if not errors else "has_errors",
        "total": len(rows),
        "rows": clean if not errors else [],
        "errors": errors[:500],
        "error_count": len(errors),
        "committed": 0,
        "created_by": ctx.user_id,
        "created_at": now,
        "expires_at": now + KEEP_FOR,
        "lock_until": None,
    }
    doc["_id"] = db.imports.insert_one(doc).inserted_id
    audit.record(
        "students.import_validated",
        actor_id=ctx.user_id,
        target_type="import",
        target_id=doc["_id"],
        details={"filename": doc["filename"], "rows": len(rows), "errors": len(errors)},
    )
    return report(doc, preview=clean[:10])


def report(doc: dict[str, Any], preview: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = {
        "id": str(doc["_id"]),
        "filename": doc["filename"],
        "status": doc["status"],
        "total": doc["total"],
        "valid": len(doc["rows"])
        if doc["status"] != "has_errors"
        else doc["total"] - len({e["row"] for e in doc["errors"]}),
        "committed": doc["committed"],
        "error_count": doc["error_count"],
        "errors": doc["errors"][:200],
    }
    if preview is not None:
        result["preview"] = [{"line": p["line"], "prn": p["prn"], "name": p["name"]} for p in preview]
    return result


def commit_chunk(ctx: AuthContext, import_id: str, ip: str) -> dict[str, Any]:
    """Creates the next CHUNK students; call again until `done` is true."""
    db = get_db()
    iid = service.oid(import_id, "Import")
    now = datetime.now(UTC)
    claimed = db.imports.find_one_and_update(
        {
            "_id": iid,
            "created_by": ctx.user_id,
            "status": {"$in": ["validated", "committing"]},
            "$or": [{"lock_until": None}, {"lock_until": {"$lt": now}}],
        },
        {"$set": {"status": "committing", "lock_until": now + timedelta(minutes=2)}},
        return_document=True,
    )
    if not claimed:
        existing = db.imports.find_one({"_id": iid, "created_by": ctx.user_id})
        if not existing:
            raise AppError(404, "Import not found (it may have expired; upload the file again).")
        if existing["status"] == "done":
            return {**report(existing), "done": True, "credentials": []}
        if existing["status"] == "has_errors":
            raise AppError(409, "Fix the errors in the file and upload it again.", "conflict")
        raise AppError(409, "This import is already running in another window.", "conflict")

    start = claimed["committed"]
    batch = claimed["rows"][start : start + CHUNK]
    credentials: list[dict[str, str]] = []

    def work(session) -> None:
        credentials.clear()
        for row in batch:
            body = StudentCreate.model_validate({k: v for k, v in row.items() if k != "line"})
            fields = service.fields_to_doc(ctx, body.model_dump(exclude_none=True))
            fields.setdefault("status", "active")
            service.check_placement(fields)
            temp = temporary_password()
            user = users_repo.create_user(
                kind="student",
                name=body.name,
                roles=["student"],
                password_hash=hash_password(temp),
                must_change_password=True,
                created_by=ctx.user_id,
                prn=body.prn,
                email=fields.get("email"),
                phone=fields.get("phone"),
                session=session,
            )
            stamp = datetime.now(UTC)
            student_id = db.students.insert_one(
                {
                    **fields,
                    "prn": body.prn,
                    "user_id": user["_id"],
                    "documents": [],
                    "created_at": stamp,
                    "created_by": ctx.user_id,
                    "updated_at": stamp,
                    "import_id": iid,
                },
                session=session,
            ).inserted_id
            audit.record(
                "students.imported",
                actor_id=ctx.user_id,
                target_type="student",
                target_id=student_id,
                ip=ip,
                details={"import_id": str(iid), "row": row["line"]},
                session=session,
            )
            credentials.append({"prn": body.prn, "name": body.name, "temporary_password": temp})
        committed = start + len(batch)
        done = committed >= len(claimed["rows"])
        db.imports.update_one(
            {"_id": iid},
            {"$set": {"committed": committed, "status": "done" if done else "committing", "lock_until": None}},
            session=session,
        )

    try:
        run_in_transaction(work)
    except AppError:
        db.imports.update_one({"_id": iid}, {"$set": {"lock_until": None}})
        raise
    updated = db.imports.find_one({"_id": iid})
    assert updated is not None
    return {**report(updated), "done": updated["status"] == "done", "credentials": credentials}


# --- promotion ------------------------------------------------------------------------------


def promote(
    ctx: AuthContext,
    programme_id: str,
    from_year: int,
    hold_back: list[str],
    dry_run: bool,
    reason: str | None,
    ip: str,
) -> dict[str, Any]:
    """Moves a year's active students up one year (the final year graduates).

    Each student is promoted at most once per academic year, so running FY before SY can't
    push anyone up two years."""
    db = get_db()
    current = db.academic_years.find_one({"is_current": True})
    if not current:
        raise AppError(409, "Set the current academic year (College setup) before promoting.", "conflict")
    programme = db.programmes.find_one({"_id": service.oid(programme_id, "Programme")})
    if not programme:
        raise AppError(404, "Programme not found.")
    if not 1 <= from_year <= programme["duration_years"]:
        raise AppError(422, f"{programme['code']} has {programme['duration_years']} years.", field="from_year")
    final = from_year == programme["duration_years"]
    held = {service.oid(h) for h in hold_back}
    students = list(
        db.students.find({"programme_id": programme["_id"], "year_of_study": from_year, "status": "active"}).sort(
            "prn", ASCENDING
        )
    )
    next_divisions = {
        d["name"]: d["_id"]
        for d in db.divisions.find(
            {"programme_id": programme["_id"], "year_of_study": from_year + 1, "status": "active"}
        )
    }
    old_divisions = {d["_id"]: d["name"] for d in db.divisions.find({"programme_id": programme["_id"]})}
    plan = []
    for s in students:
        if s["_id"] in held:
            outcome = "held_back"
        elif s.get("promoted_in") == current["_id"]:
            outcome = "already_promoted"
        else:
            outcome = "graduates" if final else "promoted"
        plan.append((s, outcome))

    summary = {
        "programme": programme["code"],
        "from_year": programme["year_labels"][from_year - 1],
        "to_year": None if final else programme["year_labels"][from_year],
        "academic_year": current["name"],
        "students": [
            {"id": str(s["_id"]), "prn": s["prn"], "name": s["name"], "outcome": outcome} for s, outcome in plan
        ],
        "counts": {
            k: sum(1 for _, o in plan if o == k) for k in ("promoted", "graduates", "held_back", "already_promoted")
        },
        "dry_run": dry_run,
    }
    if dry_run:
        return summary
    if not reason or len(reason.strip()) < 5:
        raise AppError(422, "Give a reason (e.g. 'End of 2026-27, results declared').", field="reason")

    def work(session) -> None:
        now = datetime.now(UTC)
        for s, outcome in plan:
            if outcome not in {"promoted", "graduates"}:
                continue
            changes: dict[str, Any] = {"promoted_in": current["_id"], "updated_at": now, "updated_by": ctx.user_id}
            if outcome == "graduates":
                changes["status"] = "graduated"
            else:
                changes["year_of_study"] = from_year + 1
                changes["division_id"] = next_divisions.get(old_divisions.get(s.get("division_id"), ""))
            db.students.update_one({"_id": s["_id"]}, {"$set": changes}, session=session)
            before = {
                "year_of_study": s["year_of_study"],
                "division_id": s.get("division_id"),
                "status": s.get("status"),
            }
            after = {k: changes.get(k, before[k]) for k in before}
            audit.record(
                "students.promoted",
                actor_id=ctx.user_id,
                target_type="student",
                target_id=s["_id"],
                ip=ip,
                reason=reason,
                details={"before": service.jsonable(before), "after": service.jsonable(after)},
                session=session,
            )

    run_in_transaction(work)
    return summary
