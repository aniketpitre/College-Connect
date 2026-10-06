"""
Admissions, part 2 (plan 3.5): merit rounds, confirmation and cancellation.

Merit is the qualifying-exam percentage (ties: who submitted first). A round fills a
programme's seats in two passes, the usual way for Indian reservation:
  1. open seats go to the best applicants of any category;
  2. each reserved category's seats go to the best remaining applicants of that category.
Seats already taken (an offer still open, or a confirmed admission) are not offered again; an
offer not confirmed by its date lapses, and its seat goes back into the next round. Everyone
not offered a seat stays on the waiting list with their rank.

Confirming an offer creates, in one transaction, the student record, the student's login (with
a temporary password for the admission slip) and the year's fee demand, so nothing is typed
twice. Cancelling an admission applies the cycle's refund rules: the fee demand is reversed and
anything kept is charged, so what is refundable stays as a credit for Accounts to pay back.
"""

from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.client_session import ClientSession

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.money import format_inr
from app.core.security import temporary_password
from app.modules.admissions import service as admissions
from app.modules.admissions.schemas import ConfirmIn, RoundIn
from app.modules.fees import ledger
from app.modules.fees import service as fees
from app.modules.students import service as students

register_indexes(
    "admission_rounds",
    [IndexModel([("cycle_id", ASCENDING), ("programme_id", ASCENDING), ("number", ASCENDING)], unique=True)],
)

HOLDS_SEAT = ("offered", "admitted")


def _programme(cycle: dict[str, Any], programme_id: ObjectId) -> dict[str, Any]:
    p = next((x for x in cycle["programmes"] if x["programme_id"] == programme_id), None)
    if not p:
        raise AppError(404, "This programme isn't part of the admission.")
    return p


def lapse_offers(cycle_id: ObjectId, programme_id: ObjectId) -> int:
    """Offers whose date has passed lapse; their seats are free again."""
    return (
        get_db()
        .applications.update_many(
            {
                "cycle_id": cycle_id,
                "programme_id": programme_id,
                "status": "offered",
                "offer.accept_by": {"$lt": clock.today().isoformat()},
            },
            {"$set": {"status": "lapsed"}},
        )
        .modified_count
    )


def seats(cycle: dict[str, Any], programme_id: ObjectId) -> dict[str, Any]:
    """Seats per kind (open / each reserved category), and how many are taken."""
    p = _programme(cycle, programme_id)
    taken: dict[str, int] = {}
    for a in get_db().applications.find(
        {"cycle_id": cycle["_id"], "programme_id": programme_id, "status": {"$in": list(HOLDS_SEAT)}}, {"offer": 1}
    ):
        seat = (a.get("offer") or {}).get("seat", "open")
        taken[seat] = taken.get(seat, 0) + 1
    total = {"open": p["seats"] - sum(p["reserved"].values()), **p["reserved"]}
    return {"total": total, "taken": taken, "left": {k: max(0, n - taken.get(k, 0)) for k, n in total.items()}}


def _ranked(cycle_id: ObjectId, programme_id: ObjectId) -> list[dict[str, Any]]:
    rows = list(
        get_db().applications.find(
            {"cycle_id": cycle_id, "programme_id": programme_id, "status": {"$in": ["verified", "waiting"]}}
        )
    )
    return sorted(
        rows, key=lambda a: (-(a.get("merit_score") or 0), a.get("submitted_at") or datetime.max.replace(tzinfo=UTC))
    )


def _row(a: dict[str, Any], cats: dict[ObjectId, str], **extra: Any) -> dict[str, Any]:
    return {
        "application_id": str(a["_id"]),
        "number": a.get("number"),
        "name": a["personal"].get("name"),
        "category": cats.get(a["personal"].get("category_id"), "?"),
        "merit_score": a.get("merit_score"),
        **extra,
    }


def make_round(ctx: AuthContext, cycle_id: str, body: RoundIn, ip: str) -> dict[str, Any]:
    from app.modules.messaging import service as messaging

    cycle = admissions.get_cycle(cycle_id)
    programme_id = admissions.oid(body.programme_id, "Programme")
    _programme(cycle, programme_id)
    if body.accept_by < clock.today():
        raise AppError(422, "The last date to confirm can't be in the past.", field="accept_by")
    db = get_db()
    lapsed = 0 if body.dry_run else lapse_offers(cycle["_id"], programme_id)
    left = dict(seats(cycle, programme_id)["left"])
    cats = {c["_id"]: c["code"] for c in db.categories.find({}, {"code": 1})}
    ranked = _ranked(cycle["_id"], programme_id)
    offers: list[tuple[dict[str, Any], str, int]] = []
    chosen: set[ObjectId] = set()
    for rank, a in enumerate(ranked, 1):  # 1. open seats, on merit alone
        if left.get("open", 0) > 0:
            offers.append((a, "open", rank))
            chosen.add(a["_id"])
            left["open"] -= 1
    for rank, a in enumerate(ranked, 1):  # 2. reserved seats, within each category
        cat = str(a["personal"].get("category_id"))
        if a["_id"] not in chosen and left.get(cat, 0) > 0:
            offers.append((a, cat, rank))
            chosen.add(a["_id"])
            left[cat] -= 1
    waiting = [(a, rank) for rank, a in enumerate(ranked, 1) if a["_id"] not in chosen]
    label = lambda seat: "Open" if seat == "open" else f"{cats.get(ObjectId(seat), '?')} reserved"  # noqa: E731
    result = {
        "dry_run": body.dry_run,
        "accept_by": body.accept_by.isoformat(),
        "offers": [_row(a, cats, seat=seat, seat_label=label(seat), rank=rank) for a, seat, rank in offers],
        "waiting": [_row(a, cats, rank=rank) for a, rank in waiting],
        "seats_left_after": left,
        "lapsed": lapsed,
    }
    if body.dry_run:
        return result
    if not offers:
        raise AppError(409, "No seats are free, or no verified applicants are waiting.", "nothing_to_offer")
    now = datetime.now(UTC)

    def work(session: ClientSession) -> int:
        number = (
            db.admission_rounds.count_documents(
                {"cycle_id": cycle["_id"], "programme_id": programme_id}, session=session
            )
            + 1
        )
        db.admission_rounds.insert_one(
            {
                "cycle_id": cycle["_id"],
                "programme_id": programme_id,
                "number": number,
                "accept_by": body.accept_by.isoformat(),
                "offers": [{"application_id": a["_id"], "seat": seat, "rank": rank} for a, seat, rank in offers],
                "waiting": [a["_id"] for a, _ in waiting],
                "created_at": now,
                "created_by": ctx.user_id,
            },
            session=session,
        )
        for a, seat, rank in offers:
            offer = {
                "round": number,
                "seat": seat,
                "seat_label": label(seat),
                "accept_by": body.accept_by.isoformat(),
                "offered_at": now,
            }
            db.applications.update_one(
                {"_id": a["_id"]}, {"$set": {"status": "offered", "offer": offer, "rank": rank}}, session=session
            )
        for a, rank in waiting:
            db.applications.update_one(
                {"_id": a["_id"]}, {"$set": {"status": "waiting", "rank": rank}}, session=session
            )
        audit.record(
            "admissions.round_published",
            actor_id=ctx.user_id,
            target_type="admission_cycle",
            target_id=cycle["_id"],
            ip=ip,
            details={"round": number, "offers": len(offers), "waiting": len(waiting)},
            session=session,
        )
        return number

    result["round"] = run_in_transaction(work)
    prog = db.programmes.find_one({"_id": programme_id}, {"name": 1}) or {}
    when = body.accept_by.strftime("%d %b %Y")
    for a, _, _ in offers:
        user = db.users.find_one({"_id": a["user_id"]})
        if user:
            messaging.send_to(
                user, "admission_offer", {"student": a["personal"]["name"], "programme": prog.get("name"), "date": when}
            )
    return result


def rounds(cycle_id: str, programme_id: str) -> dict[str, Any]:
    cycle = admissions.get_cycle(cycle_id)
    pid = admissions.oid(programme_id, "Programme")
    rows = get_db().admission_rounds.find({"cycle_id": cycle["_id"], "programme_id": pid}).sort("number", ASCENDING)
    return {
        "seats": seats(cycle, pid),
        "rounds": [
            {
                "number": r["number"],
                "accept_by": r["accept_by"],
                "offers": len(r["offers"]),
                "waiting": len(r["waiting"]),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }


# --- confirmation ---------------------------------------------------------------------------


def _next_prn(year_name: str, programme_code: str, session: ClientSession) -> str:
    """e.g. 2026BCA001 — the next number not already used (imported students keep theirs)."""
    db = get_db()
    start = year_name[:4]
    while True:
        counter = db.counters.find_one_and_update(
            {"_id": f"prn:{start}:{programme_code}"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        assert counter is not None
        prn = f"{start}{programme_code}{counter['seq']:03d}"
        if not db.students.find_one({"prn": prn}, {"_id": 1}, session=session):
            return prn


def confirm(ctx: AuthContext, application_id: str, body: ConfirmIn, ip: str) -> dict[str, Any]:
    from app.modules.messaging import service as messaging

    a = admissions.get_application(application_id)
    if a["status"] != "offered":
        raise AppError(409, "Only an offered seat can be confirmed.", "conflict")
    if a["offer"]["accept_by"] < clock.today().isoformat():
        raise AppError(409, "This offer has lapsed.", "lapsed")
    db = get_db()
    cycle = admissions.get_cycle(a["cycle_id"])
    year = db.academic_years.find_one({"_id": cycle["academic_year_id"]})
    programme = db.programmes.find_one({"_id": a["programme_id"]})
    assert year and programme
    year_of_study = a.get("year_of_study", 1)
    division_id = admissions.oid(body.division_id, "Division") if body.division_id else None
    if division_id is None:
        divisions = list(
            db.divisions.find(
                {"programme_id": programme["_id"], "year_of_study": year_of_study, "status": "active"}, {"_id": 1}
            )
        )
        division_id = divisions[0]["_id"] if len(divisions) == 1 else None
    p = a["personal"]
    fields = {
        k: v
        for k, v in {
            "name": p.get("name"),
            "mother_name": p.get("mother_name"),
            "gender": p.get("gender"),
            "dob": p.get("dob"),
            "email": p.get("email"),
            "phone": p.get("phone"),
            "category_id": p.get("category_id"),
            "apaar_id": p.get("apaar_id"),
            "address": p.get("address"),
            "guardian": p.get("guardian"),
            "previous_education": p.get("previous_education"),
        }.items()
        if v
    }
    fields.update(
        programme_id=programme["_id"],
        year_of_study=year_of_study,
        division_id=division_id,
        roll_no=body.roll_no,
        admission_date=(body.admission_date or clock.today()).isoformat(),
        status="active",
        application_id=a["_id"],
    )
    fields = {k: v for k, v in fields.items() if v is not None}
    students.check_placement(fields)
    structure = fees.structure_for(year["_id"], programme["_id"], year_of_study, fields.get("category_id"))
    documents = [
        {
            **{k: d[k] for k in ("id", "type", "file_id", "filename")},
            "status": "verified",
            "uploaded_at": datetime.now(UTC),
            "uploaded_by": a["user_id"],
        }
        for d in a.get("documents", [])
        if d["status"] == "verified"
    ]
    temp = temporary_password()

    def work(session: ClientSession) -> dict[str, Any]:
        current = db.applications.find_one({"_id": a["_id"]}, session=session)
        if not current or current["status"] != "offered":
            raise AppError(409, "This application changed meanwhile. Reload it.", "conflict")
        prn = body.prn.strip().upper() if body.prn else _next_prn(year["name"], programme["code"], session)
        student = students.insert(ctx, prn, fields["name"], fields, temp, ip, session, documents=documents)
        for d in documents:  # the files now belong to the student record
            db.files.update_one({"_id": d["file_id"]}, {"$set": {"student_id": student["_id"]}}, session=session)
        demand = fees.post_demand(student["_id"], year["_id"], structure, ctx.user_id, session) if structure else None
        db.applications.update_one(
            {"_id": a["_id"]},
            {
                "$set": {
                    "status": "admitted",
                    "student_id": student["_id"],
                    "prn": prn,
                    "admitted_at": datetime.now(UTC),
                    "admitted_by": ctx.user_id,
                }
            },
            session=session,
        )
        audit.record(
            "admissions.confirmed",
            actor_id=ctx.user_id,
            target_type="application",
            target_id=a["_id"],
            ip=ip,
            details={"prn": prn, "student_id": str(student["_id"]), "demand": demand["amount"] if demand else None},
            session=session,
        )
        return {"student": student, "prn": prn, "demand": demand}

    done = run_in_transaction(work)
    user = db.users.find_one({"_id": a["user_id"]})
    if user:
        messaging.send_to(
            user, "admission_confirmed", {"student": p["name"], "programme": programme["name"], "prn": done["prn"]}
        )
    return {
        "application": admissions.view(admissions.get_application(application_id), staff=True),
        "student_id": str(done["student"]["_id"]),
        "prn": done["prn"],
        "temporary_password": temp,
        "fee_demand": done["demand"]["amount"] if done["demand"] else None,
        "warning": None
        if structure
        else "No fee structure for this class and category yet: create it, then generate the demand.",
    }


# --- cancellation ---------------------------------------------------------------------------


def refund_quote(a: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    cycle = admissions.get_cycle(a["cycle_id"])
    today = today or clock.today()
    rows = ledger.entries(a["student_id"], cycle["academic_year_id"])
    paid = ledger.summary(rows, today)["paid"]
    days_before = (date.fromisoformat(cycle["course_start"]) - today).days
    percent = next((r["percent"] for r in cycle["refund_rules"] if days_before >= r["days_before"]), 0)
    refundable = max(0, paid * percent // 100 - cycle["processing_fee"]) if paid else 0
    return {
        "paid": paid,
        "days_before_start": days_before,
        "percent": percent,
        "processing_fee": cycle["processing_fee"],
        "refundable": refundable,
        "kept": paid - refundable,
    }


def cancel(ctx: AuthContext, application_id: str, reason: str, ip: str) -> dict[str, Any]:
    a = admissions.get_application(application_id)
    if a["status"] != "admitted":
        raise AppError(409, "Only a confirmed admission can be cancelled.", "conflict")
    quote = refund_quote(a)
    cycle = admissions.get_cycle(a["cycle_id"])
    db = get_db()

    def work(session: ClientSession) -> None:
        rows = ledger.entries(a["student_id"], cycle["academic_year_id"], session=session)
        demand = next((e for e in rows if e["type"] == "demand"), None)
        if demand:
            ledger.post(
                student_id=a["student_id"],
                academic_year_id=cycle["academic_year_id"],
                type="reversal",
                lines=[{"head_id": ln["head_id"], "amount": -ln["amount"]} for ln in demand["lines"]],
                created_by=ctx.user_id,
                session=session,
                ref={"type": "admission_cancelled", "id": a["_id"]},
                reason=f"Admission cancelled: {reason}",
                reverses=demand["_id"],
            )
        if quote["kept"] > 0:
            head = (demand or rows[0])["lines"][0]["head_id"] if (demand or rows) else None
            if head is not None:
                ledger.post(
                    student_id=a["student_id"],
                    academic_year_id=cycle["academic_year_id"],
                    type="charge",
                    lines=[{"head_id": head, "amount": quote["kept"]}],
                    created_by=ctx.user_id,
                    session=session,
                    reason=(
                        f"Cancellation charges ({quote['percent']}% refund, "
                        f"processing fee {format_inr(quote['processing_fee'])})"
                    ),
                )
        student = db.students.find_one({"_id": a["student_id"]}, session=session)
        assert student is not None
        db.students.update_one(
            {"_id": student["_id"]}, {"$set": {"status": "cancelled", "updated_at": datetime.now(UTC)}}, session=session
        )
        db.users.update_one({"_id": student["user_id"]}, {"$set": {"read_only": True}}, session=session)
        db.applications.update_one(
            {"_id": a["_id"]},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(UTC),
                    "cancel_reason": reason,
                    "refund": quote,
                }
            },
            session=session,
        )
        audit.record(
            "admissions.cancelled",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            reason=reason,
            details={k: quote[k] for k in ("paid", "refundable", "kept")},
            session=session,
        )

    run_in_transaction(work)
    return {"application": admissions.view(admissions.get_application(application_id), staff=True), **quote}


# --- report ---------------------------------------------------------------------------------


def report(cycle_id: str) -> dict[str, Any]:
    cycle = admissions.get_cycle(cycle_id)
    db = get_db()
    cats = {str(c["_id"]): c["code"] for c in db.categories.find({}, {"code": 1})}
    progs = {p["_id"]: p for p in db.programmes.find({}, {"code": 1, "name": 1})}
    out = []
    for p in cycle["programmes"]:
        counts: dict[str, int] = {}
        by_cat: dict[str, dict[str, int]] = {}
        for a in db.applications.find(
            {"cycle_id": cycle["_id"], "programme_id": p["programme_id"]}, {"status": 1, "personal.category_id": 1}
        ):
            counts[a["status"]] = counts.get(a["status"], 0) + 1
            cat = cats.get(str(a["personal"].get("category_id")), "?")
            row = by_cat.setdefault(cat, {"applied": 0, "admitted": 0})
            if a["status"] != "draft":
                row["applied"] += 1
            if a["status"] == "admitted":
                row["admitted"] += 1
        out.append(
            {
                "programme_id": str(p["programme_id"]),
                "programme": progs.get(p["programme_id"], {}).get("code"),
                "seats": p["seats"],
                "reserved": {cats.get(k, "?"): n for k, n in p["reserved"].items()},
                "applied": sum(n for s, n in counts.items() if s != "draft"),
                "drafts": counts.get("draft", 0),
                "verified": sum(
                    counts.get(s, 0) for s in ("verified", "waiting", "offered", "admitted", "lapsed", "cancelled")
                ),
                "offered": counts.get("offered", 0),
                "admitted": counts.get("admitted", 0),
                "waiting": counts.get("waiting", 0),
                "cancelled": counts.get("cancelled", 0),
                "by_category": by_cat,
            }
        )
    return {"cycle": cycle["name"], "programmes": out}
