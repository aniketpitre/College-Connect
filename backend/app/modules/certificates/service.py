"""
Certificates (spec §3.9, unique features U2 + U6, plan 2.9–2.10).

A student (or the office for them) asks for a certificate. Each type has a promised number of
working days (Sundays and college holidays don't count); the student sees the promised date.
Requested → verified (office; TC and migration need no dues) → signed (by the office, the
Principal or the HOD, depending on the type) → issued (gap-free number, QR verify code, PDF
made on demand). Any step can reject with a reason. The daily job escalates overdue requests
to the Principal. Issuing a TC marks the student as left and makes their login read-only.
"""

import secrets
from datetime import date, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.email import send_email
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.certificates.schemas import OfficeRequestIn, RequestIn, TypeUpdate
from app.modules.fees import ledger
from app.modules.setup import service as setup
from app.modules.timetable import service as timetable

register_indexes(
    "certificate_requests",
    [
        IndexModel([("status", ASCENDING), ("due_date", ASCENDING)]),
        IndexModel([("student_id", ASCENDING), ("requested_at", DESCENDING)]),
    ],
)
register_indexes(
    "certificates",
    [IndexModel([("verify_code", ASCENDING)], unique=True), IndexModel([("number", ASCENDING)], unique=True)],
)

TYPES: dict[str, dict[str, Any]] = {
    "bonafide": {"name": "Bonafide certificate", "days": 2, "signer": "office"},
    "character": {"name": "Character certificate", "days": 3, "signer": "office"},
    "fee_paid": {"name": "Fee-paid letter", "days": 2, "signer": "office"},
    "tc": {"name": "Transfer certificate (TC)", "days": 7, "signer": "principal", "no_dues": True, "final": True},
    "migration": {"name": "Migration certificate", "days": 7, "signer": "principal", "no_dues": True},
    "noc": {"name": "No-objection certificate (internship)", "days": 3, "signer": "hod"},
}
SIGNER_LABEL = {"office": "Registrar", "principal": "Principal", "hod": "Head of Department"}
STATUS_LABELS = {
    "requested": "Requested",
    "verified": "Verified by the office",
    "signed": "Signed",
    "ready": "Ready",
    "rejected": "Rejected",
}
OPEN = ("requested", "verified", "signed")


# --- types ----------------------------------------------------------------------------------


def types() -> list[dict[str, Any]]:
    overrides = {t["_id"]: t for t in get_db().certificate_types.find({})}
    out = []
    for key, t in TYPES.items():
        o = overrides.get(key, {})
        out.append(
            {
                "type": key,
                "name": t["name"],
                "promised_days": o.get("promised_days", t["days"]),
                "enabled": o.get("enabled", True),
                "signer": t["signer"],
                "signer_label": SIGNER_LABEL[t["signer"]],
                "no_dues": bool(t.get("no_dues")),
            }
        )
    return out


def update_type(ctx: AuthContext, key: str, body: TypeUpdate, ip: str) -> list[dict[str, Any]]:
    if P.CERT_MANAGE not in ctx.permissions:
        raise AppError(403, "Only the office changes certificate settings.", "forbidden")
    if key not in TYPES:
        raise AppError(404, "Unknown certificate.")
    get_db().certificate_types.update_one(
        {"_id": key}, {"$set": {"promised_days": body.promised_days, "enabled": body.enabled}}, upsert=True
    )
    audit.record(
        "certificates.type_updated", actor_id=ctx.user_id, target_type="certificate_type", target_id=key, ip=ip,
        details=body.model_dump(),
    )  # fmt: skip
    return types()


def _type(key: str) -> dict[str, Any]:
    t = next((x for x in types() if x["type"] == key), None)
    if not t or not t["enabled"]:
        raise AppError(422, "This certificate can't be requested right now.", field="type")
    return t


def add_working_days(start: date, days: int) -> date:
    """`days` working days after `start`: Sundays and the college's holidays don't count."""
    holidays = set(timetable.holidays_between(start, start + timedelta(days=days * 3 + 14)))
    d, left = start, days
    while left > 0:
        d += timedelta(days=1)
        if d.isoweekday() != 7 and d.isoformat() not in holidays:
            left -= 1
    return d


# --- dues -----------------------------------------------------------------------------------


def dues(student_id: ObjectId) -> list[dict[str, Any]]:
    """Every academic year in which the student still owes fees (library and hostel join in Phase 3)."""
    db = get_db()
    out = []
    for year_id in db.ledger_entries.distinct("academic_year_id", {"student_id": student_id}):
        balance = ledger.summary(ledger.entries(student_id, year_id))["balance"]
        if balance > 0:
            year = db.academic_years.find_one({"_id": year_id}, {"name": 1}) or {}
            out.append({"what": f"Fees {year.get('name', '')}".strip(), "amount": balance})
    return out


# --- requests -------------------------------------------------------------------------------


def _student(student_id: ObjectId) -> dict[str, Any]:
    s = get_db().students.find_one({"_id": student_id})
    if not s:
        raise AppError(404, "Student not found.")
    return s


def _create(ctx: AuthContext, student: dict[str, Any], body: RequestIn, ip: str, by_office: bool) -> dict[str, Any]:
    t = _type(body.type)
    if body.type == "noc" and not (body.organisation and body.from_date and body.to_date):
        raise AppError(422, "Give the organisation and the internship dates.", field="organisation")
    if t["no_dues"] and not (body.reason_for_leaving and body.reason_for_leaving.strip()):
        raise AppError(422, "Give the reason for leaving.", field="reason_for_leaving")
    db = get_db()
    if db.certificate_requests.find_one(
        {"student_id": student["_id"], "type": body.type, "status": {"$in": list(OPEN)}}
    ):
        raise AppError(409, f"A {t['name'].lower()} request is already in progress.", "conflict")
    today = clock.today()
    doc = {
        "student_id": student["_id"],
        "type": body.type,
        "purpose": body.purpose.strip(),
        "details": {
            k: (v.isoformat() if isinstance(v, date) else v)
            for k, v in body.model_dump(include={"reason_for_leaving", "organisation", "from_date", "to_date"}).items()
            if v
        },
        "status": "requested",
        "requested_at": clock.now(),
        "requested_by": ctx.user_id,
        "by_office": by_office,
        "due_date": add_working_days(today, t["promised_days"]).isoformat(),
        "history": [{"at": clock.now(), "by": ctx.user_id, "status": "requested"}],
    }
    doc["_id"] = db.certificate_requests.insert_one(doc).inserted_id
    audit.record(
        "certificates.requested", actor_id=ctx.user_id, target_type="student", target_id=student["_id"], ip=ip,
        details={"type": body.type, "due": doc["due_date"]},
    )  # fmt: skip
    return view(doc)


def request_mine(ctx: AuthContext, body: RequestIn, ip: str) -> dict[str, Any]:
    from app.modules.students import service as students

    return _create(ctx, students.my_student(ctx), body, ip, by_office=False)


def request_for(ctx: AuthContext, body: OfficeRequestIn, ip: str) -> dict[str, Any]:
    if P.CERT_MANAGE not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return _create(ctx, _student(timetable.oid(body.student_id, "Student", "student_id")), body, ip, by_office=True)


def view(r: dict[str, Any], students: dict[ObjectId, dict[str, Any]] | None = None) -> dict[str, Any]:
    t = TYPES[r["type"]]
    s = (
        (students or {}).get(r["student_id"])
        or get_db().students.find_one({"_id": r["student_id"]}, {"name": 1, "prn": 1, "division_id": 1})
        or {}
    )
    overdue = r["status"] in OPEN and clock.today().isoformat() > r["due_date"]
    return {
        "id": str(r["_id"]),
        "type": r["type"],
        "type_name": t["name"],
        "signer": t["signer"],
        "signer_label": SIGNER_LABEL[t["signer"]],
        "student_id": str(r["student_id"]),
        "student": s.get("name"),
        "prn": s.get("prn"),
        "purpose": r["purpose"],
        "details": r.get("details", {}),
        "status": r["status"],
        "status_label": STATUS_LABELS[r["status"]],
        "requested_at": r["requested_at"].isoformat(),
        "due_date": r["due_date"],
        "overdue": overdue,
        "escalated": bool(r.get("escalated_at")),
        "reason": r.get("reason"),
        "dues": r.get("dues"),
        "certificate_id": str(r["certificate_id"]) if r.get("certificate_id") else None,
        "number": r.get("number"),
    }


def mine(ctx: AuthContext) -> dict[str, Any]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    rows = get_db().certificate_requests.find({"student_id": student["_id"]}).sort("requested_at", DESCENDING)
    return {"types": [t for t in types() if t["enabled"]], "requests": [view(r) for r in rows]}


def _can_sign(ctx: AuthContext, r: dict[str, Any]) -> bool:
    signer = TYPES[r["type"]]["signer"]
    if signer == "office":
        return P.CERT_MANAGE in ctx.permissions
    if signer == "principal":
        return P.CERT_SIGN_PRINCIPAL in ctx.permissions
    student = get_db().students.find_one({"_id": r["student_id"]}, {"division_id": 1})
    division = get_db().divisions.find_one({"_id": (student or {}).get("division_id")})
    dept = ctx.user.get("department_id")
    if P.CERT_SIGN_HOD not in ctx.permissions or not division or dept is None:
        return False
    return timetable.department_of(division) == dept


def queue(ctx: AuthContext, status: str | None) -> list[dict[str, Any]]:
    """Office/readers: every request; Principal/HOD signers: those waiting for their signature (plus overdue)."""
    db = get_db()
    query: dict[str, Any] = {}
    if status == "open":
        query["status"] = {"$in": list(OPEN)}
    elif status:
        query["status"] = status
    rows = list(
        db.certificate_requests.find(query).sort([("due_date", ASCENDING), ("requested_at", ASCENDING)]).limit(500)
    )
    if not ctx.permissions & {P.CERT_MANAGE, P.CERT_READ}:
        if not ctx.permissions & {P.CERT_SIGN_HOD, P.CERT_SIGN_PRINCIPAL}:
            raise AppError(403, "You don't have permission to do this.", "forbidden")
        rows = [r for r in rows if _can_sign(ctx, r)]
    students = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [r["student_id"] for r in rows]}}, {"name": 1, "prn": 1})
    }
    out = []
    for r in rows:
        v = view(r, students)
        v["can"] = {
            "verify": P.CERT_MANAGE in ctx.permissions and r["status"] == "requested",
            "sign": r["status"] == "verified" and _can_sign(ctx, r),
            "issue": P.CERT_MANAGE in ctx.permissions and r["status"] == "signed",
            "reject": r["status"] in OPEN
            and (P.CERT_MANAGE in ctx.permissions or (r["status"] == "verified" and _can_sign(ctx, r))),
        }
        out.append(v)
    return out


def act(ctx: AuthContext, request_id: str, action: str, reason: str | None, ip: str) -> dict[str, Any]:
    db = get_db()
    r = db.certificate_requests.find_one({"_id": timetable.oid(request_id, "Request")})
    if not r:
        raise AppError(404, "Request not found.")
    t = TYPES[r["type"]]
    changes: dict[str, Any] = {}
    if action == "verify":
        if P.CERT_MANAGE not in ctx.permissions or r["status"] != "requested":
            raise AppError(403, "You can't verify this request now.", "forbidden")
        if t.get("no_dues"):
            owed = dues(r["student_id"])
            if owed:
                db.certificate_requests.update_one({"_id": r["_id"]}, {"$set": {"dues": owed}})
                total = sum(d["amount"] for d in owed) / 100
                raise AppError(
                    409,
                    f"The student still owes Rs. {total:,.2f}. Clear the dues before a {t['name']}.",
                    "dues_pending",
                )
        changes = {"status": "verified", "dues": []}
    elif action == "sign":
        if r["status"] != "verified" or not _can_sign(ctx, r):
            raise AppError(403, f"This certificate is signed by the {SIGNER_LABEL[t['signer']]}.", "forbidden")
        changes = {"status": "signed", "signed_by": ctx.user_id, "signed_at": clock.now()}
    elif action == "reject":
        allowed = r["status"] in OPEN and (
            P.CERT_MANAGE in ctx.permissions or (r["status"] == "verified" and _can_sign(ctx, r))
        )
        if not allowed:
            raise AppError(403, "You can't reject this request.", "forbidden")
        if not (reason and reason.strip()):
            raise AppError(422, "Give a reason; the student sees it.", field="reason")
        changes = {"status": "rejected", "reason": reason.strip()}
    elif action == "issue":
        if P.CERT_MANAGE not in ctx.permissions or r["status"] != "signed":
            raise AppError(403, "Only signed certificates are issued.", "forbidden")
        return _issue(ctx, r, ip)
    updated = db.certificate_requests.find_one_and_update(
        {"_id": r["_id"], "status": r["status"]},
        {
            "$set": changes,
            "$push": {"history": {"at": clock.now(), "by": ctx.user_id, "status": changes["status"], "reason": reason}},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise AppError(409, "This request changed in the meantime. Reload.", "conflict")
    audit.record(
        f"certificates.{action}", actor_id=ctx.user_id, target_type="student", target_id=r["student_id"], ip=ip,
        reason=reason, details={"type": r["type"], "request_id": str(r["_id"])},
    )  # fmt: skip
    return view(updated)


_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _issue(ctx: AuthContext, r: dict[str, Any], ip: str) -> dict[str, Any]:
    db = get_db()
    student = _student(r["student_id"])
    year = setup.current_year()
    year_name = year["name"] if year else str(clock.today().year)
    prefix = setup.institution().get("certificate_prefix") or "C"
    snapshot = _snapshot(student, r)

    def work(session: Any) -> dict[str, Any]:
        fresh = db.certificate_requests.find_one({"_id": r["_id"], "status": "signed"}, session=session)
        if not fresh:
            raise AppError(409, "This request changed in the meantime. Reload.", "conflict")
        counter = db.counters.find_one_and_update(
            {"_id": f"certificate:{year_name}"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        assert counter is not None  # upsert always returns the document
        number = f"{prefix}/{year_name}/{counter['seq']:05d}"
        cert = {
            "request_id": r["_id"],
            "student_id": student["_id"],
            "type": r["type"],
            "number": number,
            "verify_code": "".join(secrets.choice(_CODE) for _ in range(12)),
            "issued_at": clock.now(),
            "issued_by": ctx.user_id,
            "signed_by": r.get("signed_by"),
            "status": "valid",
            "data": snapshot,
        }
        cert["_id"] = db.certificates.insert_one(cert, session=session).inserted_id
        db.certificate_requests.update_one(
            {"_id": r["_id"]},
            {
                "$set": {
                    "status": "ready",
                    "certificate_id": cert["_id"],
                    "number": number,
                    "issued_at": cert["issued_at"],
                },
                "$push": {"history": {"at": clock.now(), "by": ctx.user_id, "status": "ready"}},
            },
            session=session,
        )
        if TYPES[r["type"]].get("final"):
            # A TC ends the student's time at the college: status "tc", and the login turns read-only.
            db.students.update_one(
                {"_id": student["_id"]},
                {"$set": {"status": "tc", "left_on": clock.today().isoformat()}},
                session=session,
            )
            db.users.update_one({"_id": student["user_id"]}, {"$set": {"read_only": True}}, session=session)
        return cert

    cert = run_in_transaction(work)
    audit.record(
        "certificates.issued", actor_id=ctx.user_id, target_type="student", target_id=student["_id"], ip=ip,
        details={"type": r["type"], "number": cert["number"]},
    )  # fmt: skip
    if student.get("email"):
        send_email(
            student["email"],
            f"Your {TYPES[r['type']]['name'].lower()} is ready",
            f"Dear {student['name']},\n\nYour {TYPES[r['type']]['name'].lower()} ({cert['number']}) is ready. "
            "Download it from CollegeConnect (My certificates) or collect the signed copy at the office.\n",
        )
    updated = db.certificate_requests.find_one({"_id": r["_id"]})
    assert updated is not None
    return view(updated)


def _snapshot(student: dict[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    """What the certificate states, frozen at issue time."""
    from app.modules.students import service as students

    db = get_db()
    summary = students.summary(student)
    programme = db.programmes.find_one({"_id": student.get("programme_id")}, {"name": 1}) or {}
    year = setup.current_year()
    data: dict[str, Any] = {
        "name": student["name"],
        "prn": student["prn"],
        "gender": student.get("gender"),
        "dob": student.get("dob"),
        "class": " ".join(x for x in (summary["programme_code"], summary["year_label"], summary["division"]) if x),
        "programme": programme.get("name"),
        "academic_year": year["name"] if year else None,
        "admission_date": student.get("admission_date"),
        "purpose": r["purpose"],
        **r.get("details", {}),
    }
    if r["type"] == "fee_paid" and year:
        info = ledger.summary(ledger.entries(student["_id"], year["_id"]))
        data["fees_paid"] = info["paid"]
        data["fees_due"] = max(0, info["balance"])
    return data


def certificate_for_student(ctx: AuthContext, request_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.modules.students import service as students

    student = students.my_student(ctx)
    r = get_db().certificate_requests.find_one({"_id": timetable.oid(request_id, "Request")})
    if not r or r["student_id"] != student["_id"] or not r.get("certificate_id"):
        raise AppError(404, "Certificate not found.")
    cert = get_db().certificates.find_one({"_id": r["certificate_id"]})
    assert cert is not None
    return cert, r


def certificate_for_staff(ctx: AuthContext, request_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ctx.permissions & {P.CERT_MANAGE, P.CERT_READ}:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    r = get_db().certificate_requests.find_one({"_id": timetable.oid(request_id, "Request")})
    if not r or not r.get("certificate_id"):
        raise AppError(404, "Certificate not found.")
    cert = get_db().certificates.find_one({"_id": r["certificate_id"]})
    assert cert is not None
    return cert, r


def verify(code: str) -> dict[str, Any]:
    """Public Verify page: genuine or not, with masked details."""
    cert = get_db().certificates.find_one({"verify_code": code.strip().upper()})
    if not cert:
        raise AppError(404, "No document with this code. Check the code or ask the college office.", "not_found")
    parts = cert["data"]["name"].split()
    prn = cert["data"]["prn"]
    return {
        "type": "certificate",
        "valid": cert["status"] == "valid",
        "status": cert["status"],
        "number": cert["number"],
        "date": cert["issued_at"].isoformat(),
        "certificate": TYPES[cert["type"]]["name"],
        "student_name": " ".join([parts[0], *(p[0] + "." for p in parts[1:])]),
        "prn": prn[:-3] + "***" if len(prn) > 4 else "***",
        "college": setup.institution().get("name") or "",
    }


# --- escalation (daily job) -----------------------------------------------------------------


def escalate_overdue() -> dict[str, int]:
    """Marks open requests past their promised date and emails the Principal(s) a list, once each."""
    db = get_db()
    today = clock.today().isoformat()
    late = list(
        db.certificate_requests.find(
            {"status": {"$in": list(OPEN)}, "due_date": {"$lt": today}, "escalated_at": {"$exists": False}}
        )
    )
    if not late:
        return {"escalated": 0, "emailed": 0}
    db.certificate_requests.update_many(
        {"_id": {"$in": [r["_id"] for r in late]}}, {"$set": {"escalated_at": clock.now()}}
    )
    lines = [
        f"- {v['type_name']} for {v['student']} ({v['prn']}): promised {v['due_date']}, now {v['status_label'].lower()}"
        for v in map(view, late)
    ]
    emailed = 0
    for p in db.users.find({"roles": "principal", "status": "active", "email": {"$ne": None}}, {"email": 1}):
        if send_email(
            p["email"],
            f"{len(late)} certificate request(s) are overdue",
            "These are past the date promised to students:\n\n" + "\n".join(lines) + "\n",
        ):
            emailed += 1
    audit.record("certificates.escalated", details={"requests": len(late)})
    return {"escalated": len(late), "emailed": emailed}
