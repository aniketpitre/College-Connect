"""
Hostel (spec §3.13, plan 3.7): blocks, rooms and beds, allotment with the hostel fee in the
student's fee account, out-passes approved by the warden with the parents told, complaints and
the mess menu.

A bed is allotted for the current academic year; the block's annual fee is charged once per
student per year (fee head HOSTEL). An out-pass goes requested → approved (or rejected) → out →
returned; a return after the agreed time is marked late. Approving it tells the student and
their linked parents.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.money import format_inr
from app.modules.fees import service as fees
from app.modules.hostel.schemas import BlockIn, ComplaintIn, ComplaintUpdate, MessMenu, OutpassIn
from app.modules.students import service as students

register_indexes("hostel_rooms", [IndexModel([("block_id", ASCENDING), ("number", ASCENDING)], unique=True)])
register_indexes(
    "hostel_allotments",
    [
        IndexModel([("student_id", ASCENDING)], unique=True, partialFilterExpression={"status": "active"}),
        IndexModel(
            [("room_id", ASCENDING), ("bed", ASCENDING)], unique=True, partialFilterExpression={"status": "active"}
        ),
    ],
)
register_indexes(
    "outpasses", [IndexModel([("status", ASCENDING), ("leave_at", ASCENDING)]), IndexModel([("student_id", ASCENDING)])]
)
register_indexes("hostel_complaints", [IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])])

MENU_ID = "hostel_mess"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def oid(value: Any, what: str) -> ObjectId:
    return students.oid(value, what)


# --- blocks and rooms -----------------------------------------------------------------------


def add_block(ctx: AuthContext, body: BlockIn) -> dict[str, Any]:
    db = get_db()
    if db.hostel_blocks.find_one({"name": body.name.strip()}):
        raise AppError(409, "A block with this name exists.", "conflict", "name")
    db.hostel_blocks.insert_one({**body.model_dump(), "name": body.name.strip(), "created_at": datetime.now(UTC)})
    audit.record("hostel.block_added", actor_id=ctx.user_id, details={"name": body.name})
    return overview()


def update_block(ctx: AuthContext, block_id: str, body: BlockIn) -> dict[str, Any]:
    db = get_db()
    b = db.hostel_blocks.find_one({"_id": oid(block_id, "Block")})
    if not b:
        raise AppError(404, "Block not found.")
    db.hostel_blocks.update_one({"_id": b["_id"]}, {"$set": {**body.model_dump(), "name": body.name.strip()}})
    audit.record("hostel.block_updated", actor_id=ctx.user_id, details=body.model_dump())
    return overview()


def add_rooms(ctx: AuthContext, block_id: str, numbers: list[str], beds: int) -> dict[str, Any]:
    db = get_db()
    b = db.hostel_blocks.find_one({"_id": oid(block_id, "Block")})
    if not b:
        raise AppError(404, "Block not found.")
    clean = [n.strip().upper() for n in numbers if n.strip()]
    try:
        db.hostel_rooms.insert_many([{"block_id": b["_id"], "number": n, "beds": beds} for n in clean])
    except Exception as e:  # noqa: BLE001 - duplicate room number
        raise AppError(409, "One of these rooms already exists in the block.", "conflict", "numbers") from e
    return overview()


def overview() -> dict[str, Any]:
    db = get_db()
    blocks = list(db.hostel_blocks.find({}).sort("name", ASCENDING))
    rooms = list(db.hostel_rooms.find({}).sort("number", ASCENDING))
    active = list(db.hostel_allotments.find({"status": "active"}))
    people = {
        s["_id"]: s
        for s in db.students.find({"_id": {"$in": [a["student_id"] for a in active]}}, {"name": 1, "prn": 1})
    }
    by_room: dict[ObjectId, list[dict[str, Any]]] = {}
    for a in active:
        s = people.get(a["student_id"], {})
        by_room.setdefault(a["room_id"], []).append(
            {
                "allotment_id": str(a["_id"]),
                "bed": a["bed"],
                "name": s.get("name"),
                "prn": s.get("prn"),
                "student_id": str(a["student_id"]),
            }
        )
    out = []
    for b in blocks:
        mine = [r for r in rooms if r["block_id"] == b["_id"]]
        out.append(
            {
                "id": str(b["_id"]),
                "name": b["name"],
                "gender": b["gender"],
                "annual_fee": b["annual_fee"],
                "beds": sum(r["beds"] for r in mine),
                "occupied": sum(len(by_room.get(r["_id"], [])) for r in mine),
                "rooms": [
                    {
                        "id": str(r["_id"]),
                        "number": r["number"],
                        "beds": r["beds"],
                        "occupants": sorted(by_room.get(r["_id"], []), key=lambda x: x["bed"]),
                    }
                    for r in mine
                ],
            }
        )
    now = clock.now()
    return {
        "blocks": out,
        "pending_outpasses": db.outpasses.count_documents({"status": "requested"}),
        "out_now": db.outpasses.count_documents({"status": "out"}),
        "overdue_returns": db.outpasses.count_documents({"status": "out", "return_by": {"$lt": now}}),
        "open_complaints": db.hostel_complaints.count_documents({"status": {"$ne": "resolved"}}),
    }


# --- allotment ------------------------------------------------------------------------------


def allot(ctx: AuthContext, prn: str, room_id: str, bed: int | None, ip: str) -> dict[str, Any]:
    db = get_db()
    student = db.students.find_one({"prn": prn.strip().upper()})
    if not student or student.get("status") != "active":
        raise AppError(404, "No active student with this PRN.", field="prn")
    room = db.hostel_rooms.find_one({"_id": oid(room_id, "Room")})
    if not room:
        raise AppError(404, "Room not found.", field="room_id")
    block = db.hostel_blocks.find_one({"_id": room["block_id"]})
    assert block is not None
    if (
        block["gender"] != "any"
        and student.get("gender")
        and {"boys": "male", "girls": "female"}[block["gender"]] != student["gender"]
    ):
        raise AppError(409, f"{block['name']} is for {block['gender']}.", "wrong_block", "room_id")
    taken = {a["bed"] for a in db.hostel_allotments.find({"room_id": room["_id"], "status": "active"}, {"bed": 1})}
    free = [b for b in range(1, room["beds"] + 1) if b not in taken]
    if bed is None:
        if not free:
            raise AppError(409, "This room is full.", "full", "room_id")
        bed = free[0]
    elif bed not in free:
        raise AppError(409, "That bed is taken.", "taken", "bed")
    year = db.academic_years.find_one({"is_current": True})
    if not year:
        raise AppError(409, "Set the current academic year first.", "no_year")
    charged = db.hostel_allotments.find_one(
        {"student_id": student["_id"], "academic_year_id": year["_id"], "fee_entry_id": {"$exists": True}}
    )

    def work(session: ClientSession) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "student_id": student["_id"],
            "room_id": room["_id"],
            "block_id": block["_id"],
            "bed": bed,
            "academic_year_id": year["_id"],
            "status": "active",
            "from_date": clock.today().isoformat(),
            "allotted_by": ctx.user_id,
            "created_at": datetime.now(UTC),
        }
        if block["annual_fee"] and not charged:
            entry = fees.post_charge(
                student["_id"],
                head_code="HOSTEL",
                head_name="Hostel fee",
                amount=block["annual_fee"],
                by=ctx.user_id,
                session=session,
                year_id=year["_id"],
                reason=f"Hostel {block['name']} {year['name']}",
            )
            doc["fee_entry_id"] = entry["_id"]
        try:
            doc["_id"] = db.hostel_allotments.insert_one(doc, session=session).inserted_id
        except DuplicateKeyError as e:
            raise AppError(409, "The student already has a bed, or the bed was just taken.", "conflict") from e
        audit.record(
            "hostel.allotted",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            details={
                "block": block["name"],
                "room": room["number"],
                "bed": bed,
                "fee": block["annual_fee"] if not charged else 0,
            },
            session=session,
        )
        return doc

    run_in_transaction(work)
    return overview()


def vacate(ctx: AuthContext, allotment_id: str, reason: str, ip: str) -> dict[str, Any]:
    db = get_db()
    a = db.hostel_allotments.find_one({"_id": oid(allotment_id, "Allotment"), "status": "active"})
    if not a:
        raise AppError(404, "Allotment not found.")
    db.hostel_allotments.update_one(
        {"_id": a["_id"]},
        {"$set": {"status": "vacated", "to_date": clock.today().isoformat(), "vacate_reason": reason}},
    )
    audit.record(
        "hostel.vacated", actor_id=ctx.user_id, target_type="student", target_id=a["student_id"], ip=ip, reason=reason
    )
    return overview()


def _resident(student_id: ObjectId) -> dict[str, Any] | None:
    return get_db().hostel_allotments.find_one({"student_id": student_id, "status": "active"})


# --- out-passes -----------------------------------------------------------------------------


def _outpass_view(o: dict[str, Any], student: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "id": str(o["_id"]),
        "leave_at": o["leave_at"].isoformat(),
        "return_by": o["return_by"].isoformat(),
        "destination": o["destination"],
        "reason": o["reason"],
        "status": o["status"],
        "decision_reason": o.get("decision_reason"),
        "out_at": o["out_at"].isoformat() if o.get("out_at") else None,
        "returned_at": o["returned_at"].isoformat() if o.get("returned_at") else None,
        "late": bool(o.get("late")),
        "created_at": o["created_at"].isoformat(),
    }
    if student:
        out["student"] = {"id": str(student["_id"]), "name": student["name"], "prn": student["prn"]}
    return out


def request_outpass(ctx: AuthContext, body: OutpassIn) -> dict[str, Any]:
    student = students.my_student(ctx)
    if not _resident(student["_id"]):
        raise AppError(409, "Out-passes are for hostel residents.", "not_resident")
    leave = body.leave_at if body.leave_at.tzinfo else body.leave_at.replace(tzinfo=clock.IST)
    back = body.return_by if body.return_by.tzinfo else body.return_by.replace(tzinfo=clock.IST)
    if back < clock.now():
        raise AppError(422, "The return time has already passed.", field="return_by")
    db = get_db()
    if db.outpasses.find_one({"student_id": student["_id"], "status": {"$in": ["requested", "approved", "out"]}}):
        raise AppError(409, "You already have an open out-pass.", "conflict")
    db.outpasses.insert_one(
        {
            "student_id": student["_id"],
            "leave_at": leave,
            "return_by": back,
            "destination": body.destination.strip(),
            "reason": body.reason.strip(),
            "status": "requested",
            "created_at": datetime.now(UTC),
        }
    )
    return my_hostel(ctx)


def list_outpasses(status: str) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {"status": {"$in": ["approved", "out"]}} if status == "active" else {"status": status}
    rows = list(db.outpasses.find(query).sort("leave_at", ASCENDING if status != "returned" else DESCENDING).limit(300))
    people = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [o["student_id"] for o in rows]}}, {"name": 1, "prn": 1})
    }
    return [_outpass_view(o, people.get(o["student_id"])) for o in rows]


def act_outpass(ctx: AuthContext, outpass_id: str, action: str, reason: str | None, ip: str) -> dict[str, Any]:
    from app.modules.messaging import service as messaging

    db = get_db()
    o = db.outpasses.find_one({"_id": oid(outpass_id, "Out-pass")})
    if not o:
        raise AppError(404, "Out-pass not found.")
    allowed = {
        "approve": ["requested"],
        "reject": ["requested"],
        "out": ["approved"],
        "returned": ["out"],
        "cancel": ["requested", "approved"],
    }
    if o["status"] not in allowed[action]:
        raise AppError(409, f"This out-pass is {o['status']}.", "conflict")
    if action == "reject" and not (reason or "").strip():
        raise AppError(422, "Give a reason.", field="reason")
    now = datetime.now(UTC)
    update: dict[str, Any] = {
        "approve": {"status": "approved", "decided_by": ctx.user_id, "decided_at": now},
        "reject": {
            "status": "rejected",
            "decided_by": ctx.user_id,
            "decided_at": now,
            "decision_reason": (reason or "").strip(),
        },
        "out": {"status": "out", "out_at": now},
        "returned": {"status": "returned", "returned_at": now, "late": clock.now() > o["return_by"]},
        "cancel": {"status": "cancelled"},
    }[action]
    db.outpasses.update_one({"_id": o["_id"]}, {"$set": update})
    audit.record(
        f"hostel.outpass_{action}",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=o["student_id"],
        ip=ip,
        reason=reason,
    )
    if action == "approve":
        student = db.students.find_one({"_id": o["student_id"]})
        if student:
            fmt = "%d %b %I:%M %p"
            messaging.notify(
                student,
                "outpass_approved",
                {
                    "from": o["leave_at"].astimezone(clock.IST).strftime(fmt),
                    "to": o["return_by"].astimezone(clock.IST).strftime(fmt),
                    "place": o["destination"],
                },
            )
    updated = db.outpasses.find_one({"_id": o["_id"]})
    assert updated is not None
    return _outpass_view(updated, db.students.find_one({"_id": o["student_id"]}, {"name": 1, "prn": 1}))


# --- complaints and mess --------------------------------------------------------------------


def _complaint_view(c: dict[str, Any], student: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "id": str(c["_id"]),
        "category": c["category"],
        "text": c["text"],
        "status": c["status"],
        "room": c.get("room"),
        "notes": [{"at": n["at"].isoformat(), "text": n["text"]} for n in c.get("notes", [])],
        "created_at": c["created_at"].isoformat(),
    }
    if student:
        out["student"] = {"name": student["name"], "prn": student["prn"]}
    return out


def complain(ctx: AuthContext, body: ComplaintIn) -> dict[str, Any]:
    student = students.my_student(ctx)
    a = _resident(student["_id"])
    if not a:
        raise AppError(409, "Hostel complaints are for residents.", "not_resident")
    db = get_db()
    room = db.hostel_rooms.find_one({"_id": a["room_id"]}) or {}
    block = db.hostel_blocks.find_one({"_id": a["block_id"]}) or {}
    db.hostel_complaints.insert_one(
        {
            "student_id": student["_id"],
            "block_id": a["block_id"],
            "room": f"{block.get('name', '')} {room.get('number', '')}".strip(),
            "category": body.category,
            "text": body.text.strip(),
            "status": "open",
            "notes": [],
            "created_at": datetime.now(UTC),
        }
    )
    return my_hostel(ctx)


def list_complaints(status: str | None) -> list[dict[str, Any]]:
    db = get_db()
    query: dict[str, Any] = {"status": status} if status else {"status": {"$ne": "resolved"}}
    rows = list(db.hostel_complaints.find(query).sort("created_at", DESCENDING).limit(300))
    people = {
        s["_id"]: s for s in db.students.find({"_id": {"$in": [c["student_id"] for c in rows]}}, {"name": 1, "prn": 1})
    }
    return [_complaint_view(c, people.get(c["student_id"])) for c in rows]


def update_complaint(ctx: AuthContext, complaint_id: str, body: ComplaintUpdate) -> dict[str, Any]:
    db = get_db()
    c = db.hostel_complaints.find_one({"_id": oid(complaint_id, "Complaint")})
    if not c:
        raise AppError(404, "Complaint not found.")
    update: dict[str, Any] = {"$set": {"status": body.status}}
    if body.status == "resolved":
        update["$set"]["resolved_at"] = datetime.now(UTC)
    if body.note.strip():
        update["$push"] = {"notes": {"at": datetime.now(UTC), "by": ctx.user_id, "text": body.note.strip()}}
    db.hostel_complaints.update_one({"_id": c["_id"]}, update)
    updated = db.hostel_complaints.find_one({"_id": c["_id"]})
    assert updated is not None
    return _complaint_view(updated)


def mess_menu() -> dict[str, str]:
    doc = get_db().settings.find_one({"_id": MENU_ID}) or {}
    return {d: doc.get("days", {}).get(d, "") for d in DAYS}


def save_menu(ctx: AuthContext, body: MessMenu) -> dict[str, str]:
    get_db().settings.update_one(
        {"_id": MENU_ID}, {"$set": {"days": {k: v.strip()[:300] for k, v in body.days.items()}}}, upsert=True
    )
    audit.record("hostel.menu_changed", actor_id=ctx.user_id)
    return mess_menu()


# --- the student's own page -----------------------------------------------------------------


def my_hostel(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    db = get_db()
    a = _resident(student["_id"])
    room = block = None
    if a:
        room = db.hostel_rooms.find_one({"_id": a["room_id"]})
        block = db.hostel_blocks.find_one({"_id": a["block_id"]})
    return {
        "resident": bool(a),
        "allotment": {
            "block": block["name"] if block else None,
            "room": room["number"] if room else None,
            "bed": a["bed"],
            "since": a["from_date"],
            "annual_fee": format_inr(block["annual_fee"], "₹") if block else None,
        }
        if a
        else None,
        "outpasses": [
            _outpass_view(o)
            for o in db.outpasses.find({"student_id": student["_id"]}).sort("created_at", DESCENDING).limit(10)
        ],
        "complaints": [
            _complaint_view(c)
            for c in db.hostel_complaints.find({"student_id": student["_id"]}).sort("created_at", DESCENDING).limit(10)
        ],
        "mess_menu": mess_menu() if a else None,
    }


def dues(student_id: ObjectId) -> list[str]:
    """For the no-dues check: still holding a hostel bed."""
    a = _resident(student_id)
    return ["Hostel bed not vacated"] if a else []
