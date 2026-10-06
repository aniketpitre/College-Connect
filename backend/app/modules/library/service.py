"""
Library (spec §3.12, plan 3.6): catalogue, copies with barcodes, issue and return, fines,
reservations and overdue reminders.

A title (`books`) has copies (`book_copies`), each with a barcode the librarian scans. A loan
runs `loan_days`; a late return is fined `fine_per_day` for each day, charged straight to the
student's fee account (fee head LIBRARY), so it shows in their fees and can be paid online or
at the counter. A title with every copy out can be reserved; when a copy comes back it is held
for the first student in the queue for `hold_days`, and they are told.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError

from app.core import audit, clock
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.core.money import format_inr
from app.modules.fees import service as fees
from app.modules.library.schemas import BookIn, SettingsIn
from app.modules.students import service as students

register_indexes(
    "books",
    [
        IndexModel([("isbn", ASCENDING)], partialFilterExpression={"isbn": {"$type": "string"}}),
        IndexModel([("title", ASCENDING)]),
    ],
)
register_indexes(
    "book_copies",
    [IndexModel([("barcode", ASCENDING)], unique=True), IndexModel([("book_id", ASCENDING), ("status", ASCENDING)])],
)
register_indexes(
    "loans",
    [
        IndexModel([("student_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("status", ASCENDING), ("due_date", ASCENDING)]),
        # One open loan per copy.
        IndexModel([("copy_id", ASCENDING)], unique=True, partialFilterExpression={"status": "open"}),
    ],
)
register_indexes(
    "book_reservations",
    [
        IndexModel([("book_id", ASCENDING), ("status", ASCENDING), ("created_at", ASCENDING)]),
        IndexModel([("student_id", ASCENDING)]),
    ],
)

SETTINGS_ID = "library"
OPEN_RESERVATION = ("waiting", "ready")


def settings() -> dict[str, Any]:
    doc = get_db().settings.find_one({"_id": SETTINGS_ID}) or {}
    return SettingsIn(**{k: v for k, v in doc.items() if k in SettingsIn.model_fields}).model_dump()


def save_settings(ctx: AuthContext, body: SettingsIn) -> dict[str, Any]:
    get_db().settings.update_one({"_id": SETTINGS_ID}, {"$set": body.model_dump()}, upsert=True)
    audit.record("library.settings_changed", actor_id=ctx.user_id, details=body.model_dump())
    return settings()


def oid(value: Any, what: str) -> ObjectId:
    return students.oid(value, what)


# --- catalogue ------------------------------------------------------------------------------


def lookup_isbn(isbn: str) -> dict[str, Any]:
    """Title, authors, publisher and year from Open Library (free, no key); empty if not found."""
    try:
        res = httpx.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=5,
        )
        res.raise_for_status()
        data = res.json().get(f"ISBN:{isbn}")
    except (httpx.HTTPError, ValueError):
        return {"found": False}
    if not data:
        return {"found": False}
    year = re.search(r"\d{4}", data.get("publish_date") or "")
    return {
        "found": True,
        "isbn": isbn,
        "title": data.get("title", "")[:200],
        "authors": [a.get("name", "") for a in data.get("authors", [])][:10],
        "publisher": ((data.get("publishers") or [{}])[0].get("name") or "")[:120],
        "year": int(year.group()) if year else None,
        "subject": ((data.get("subjects") or [{}])[0].get("name") or "")[:80],
    }


def _new_barcodes(n: int, session: ClientSession | None = None) -> list[str]:
    counter = get_db().counters.find_one_and_update(
        {"_id": "library_barcode"},
        {"$inc": {"seq": n}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    assert counter is not None
    return [f"LIB{seq:06d}" for seq in range(counter["seq"] - n + 1, counter["seq"] + 1)]


def _add_copies(book_id: ObjectId, count: int, barcodes: list[str]) -> list[str]:
    codes = [b.strip().upper() for b in barcodes if b.strip()] or _new_barcodes(count)
    now = datetime.now(UTC)
    try:
        get_db().book_copies.insert_many(
            [{"book_id": book_id, "barcode": c, "status": "available", "added_at": now} for c in codes]
        )
    except Exception as e:  # noqa: BLE001 - duplicate barcode
        raise AppError(409, "One of these barcodes is already used.", "conflict", "barcodes") from e
    return codes


def add_book(ctx: AuthContext, body: BookIn) -> dict[str, Any]:
    db = get_db()
    doc: dict[str, Any] = {
        "isbn": body.isbn,
        "title": body.title.strip(),
        "authors": [a.strip() for a in body.authors if a.strip()],
        "publisher": body.publisher.strip(),
        "year": body.year,
        "subject": body.subject.strip(),
        "created_at": datetime.now(UTC),
        "created_by": ctx.user_id,
    }
    doc["_id"] = db.books.insert_one(doc).inserted_id
    if body.copies or body.barcodes:
        _add_copies(doc["_id"], body.copies, body.barcodes)
    audit.record(
        "library.book_added",
        actor_id=ctx.user_id,
        target_type="book",
        target_id=doc["_id"],
        details={"title": doc["title"]},
    )
    return book_view(doc, staff=True)


def add_copies(ctx: AuthContext, book_id: str, count: int, barcodes: list[str]) -> dict[str, Any]:
    book = get_book(book_id)
    _add_copies(book["_id"], count, barcodes)
    return book_view(book, staff=True)


def get_book(book_id: Any) -> dict[str, Any]:
    b = get_db().books.find_one({"_id": book_id if isinstance(book_id, ObjectId) else oid(book_id, "Book")})
    if not b:
        raise AppError(404, "Book not found.")
    return b


def book_view(b: dict[str, Any], *, staff: bool = False) -> dict[str, Any]:
    db = get_db()
    copies = list(db.book_copies.find({"book_id": b["_id"], "status": {"$ne": "withdrawn"}}))
    out = {
        "id": str(b["_id"]),
        "isbn": b.get("isbn"),
        "title": b["title"],
        "authors": b.get("authors", []),
        "publisher": b.get("publisher", ""),
        "year": b.get("year"),
        "subject": b.get("subject", ""),
        "copies": len(copies),
        "available": sum(1 for c in copies if c["status"] == "available"),
        "waiting": db.book_reservations.count_documents({"book_id": b["_id"], "status": "waiting"}),
    }
    if staff:
        out["copy_list"] = [
            {"barcode": c["barcode"], "status": c["status"]} for c in sorted(copies, key=lambda c: c["barcode"])
        ]
    return out


def search(q: str | None, *, staff: bool, limit: int = 50) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"authors": rx}, {"isbn": q.strip().replace("-", "")}, {"subject": rx}]
    return [book_view(b, staff=staff) for b in get_db().books.find(query).sort("title", ASCENDING).limit(limit)]


# --- circulation ----------------------------------------------------------------------------


def _student_by_prn(prn: str) -> dict[str, Any]:
    s = get_db().students.find_one({"prn": prn.strip().upper()})
    if not s:
        raise AppError(404, "No student with this PRN.", field="prn")
    if s.get("status") != "active":
        raise AppError(409, "This student is not active.", "inactive", "prn")
    return s


def _copy(barcode: str, session: ClientSession | None = None) -> dict[str, Any]:
    c = get_db().book_copies.find_one({"barcode": barcode.strip().upper()}, session=session)
    if not c:
        raise AppError(404, "No copy with this barcode.", field="barcode")
    return c


def loan_view(
    loan: dict[str, Any], book: dict[str, Any] | None = None, student: dict[str, Any] | None = None
) -> dict[str, Any]:
    book = book or get_db().books.find_one({"_id": loan["book_id"]}, {"title": 1, "authors": 1}) or {}
    today = clock.today()
    due = date.fromisoformat(loan["due_date"])
    late = max(0, (today - due).days) if loan["status"] == "open" else 0
    out = {
        "id": str(loan["_id"]),
        "book_id": str(loan["book_id"]),
        "title": book.get("title"),
        "authors": book.get("authors", []),
        "barcode": loan["barcode"],
        "issued_on": loan["issued_at"].astimezone(clock.IST).date().isoformat(),
        "due_date": loan["due_date"],
        "returned_on": loan["returned_at"].astimezone(clock.IST).date().isoformat()
        if loan.get("returned_at")
        else None,
        "status": loan["status"],
        "days_late": late,
        "fine_so_far": late * settings()["fine_per_day"],
        "fine": loan.get("fine", 0),
        "renewals": loan.get("renewals", 0),
    }
    if student:
        out.update(student={"id": str(student["_id"]), "name": student["name"], "prn": student["prn"]})
    return out


def issue(ctx: AuthContext, barcode: str, prn: str, ip: str) -> dict[str, Any]:
    rules = settings()
    student = _student_by_prn(prn)
    db = get_db()
    copy = _copy(barcode)
    if copy["status"] == "held" and copy.get("held_for") != student["_id"]:
        raise AppError(409, "This copy is kept for a student who reserved it.", "held", "barcode")
    if copy["status"] not in ("available", "held"):
        raise AppError(
            409, "This copy is not on the shelf (already issued, lost or withdrawn).", "not_available", "barcode"
        )
    open_loans = list(db.loans.find({"student_id": student["_id"], "status": "open"}, {"due_date": 1}))
    if len(open_loans) >= rules["max_books"]:
        raise AppError(
            409, f"The student already has {len(open_loans)} books (the limit is {rules['max_books']}).", "limit", "prn"
        )
    if any(lo["due_date"] < clock.today().isoformat() for lo in open_loans):
        raise AppError(409, "The student has an overdue book: return it first.", "overdue", "prn")
    now = datetime.now(UTC)
    due = (clock.today() + timedelta(days=rules["loan_days"])).isoformat()

    def work(session: ClientSession) -> dict[str, Any]:
        loan = {
            "copy_id": copy["_id"],
            "book_id": copy["book_id"],
            "barcode": copy["barcode"],
            "student_id": student["_id"],
            "issued_at": now,
            "issued_by": ctx.user_id,
            "due_date": due,
            "renewals": 0,
            "status": "open",
        }
        try:
            loan["_id"] = db.loans.insert_one(loan, session=session).inserted_id
        except DuplicateKeyError as e:
            raise AppError(409, "This copy was just issued to someone else.", "conflict", "barcode") from e
        db.book_copies.update_one(
            {"_id": copy["_id"]},
            {"$set": {"status": "issued"}, "$unset": {"held_for": "", "held_until": ""}},
            session=session,
        )
        db.book_reservations.update_many(
            {"book_id": copy["book_id"], "student_id": student["_id"], "status": {"$in": list(OPEN_RESERVATION)}},
            {"$set": {"status": "fulfilled", "closed_at": now}},
            session=session,
        )
        audit.record(
            "library.issued",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=student["_id"],
            ip=ip,
            details={"barcode": copy["barcode"], "due": due},
            session=session,
        )
        return loan

    loan = run_in_transaction(work)
    return loan_view(loan, student=student)


def _hold_or_shelve(copy: dict[str, Any], session: ClientSession) -> dict[str, Any] | None:
    """A returned copy goes to the first student waiting for the title, or back on the shelf."""
    db = get_db()
    nxt = db.book_reservations.find_one(
        {"book_id": copy["book_id"], "status": "waiting"}, sort=[("created_at", ASCENDING)], session=session
    )
    if not nxt:
        db.book_copies.update_one(
            {"_id": copy["_id"]},
            {"$set": {"status": "available"}, "$unset": {"held_for": "", "held_until": ""}},
            session=session,
        )
        return None
    until = (clock.today() + timedelta(days=settings()["hold_days"])).isoformat()
    db.book_copies.update_one(
        {"_id": copy["_id"]},
        {"$set": {"status": "held", "held_for": nxt["student_id"], "held_until": until}},
        session=session,
    )
    db.book_reservations.update_one(
        {"_id": nxt["_id"]},
        {"$set": {"status": "ready", "ready_until": until, "barcode": copy["barcode"]}},
        session=session,
    )
    return {**nxt, "ready_until": until}


def _tell_ready(reservation: dict[str, Any] | None) -> None:
    if not reservation:
        return
    from app.modules.messaging import service as messaging

    db = get_db()
    student = db.students.find_one({"_id": reservation["student_id"]})
    book = db.books.find_one({"_id": reservation["book_id"]}, {"title": 1})
    if student and book:
        when = date.fromisoformat(reservation["ready_until"]).strftime("%d %b")
        messaging.notify(student, "library_ready", {"title": book["title"], "date": when})


def return_book(ctx: AuthContext, barcode: str, ip: str) -> dict[str, Any]:
    db = get_db()
    copy = _copy(barcode)
    loan = db.loans.find_one({"copy_id": copy["_id"], "status": "open"})
    if not loan:
        raise AppError(409, "This copy isn't issued to anyone.", "not_issued", "barcode")
    rules = settings()
    days_late = max(0, (clock.today() - date.fromisoformat(loan["due_date"])).days)
    fine = days_late * rules["fine_per_day"]
    book = db.books.find_one({"_id": loan["book_id"]}, {"title": 1, "authors": 1}) or {}
    held: dict[str, Any] = {}

    def work(session: ClientSession) -> None:
        update: dict[str, Any] = {
            "status": "returned",
            "returned_at": datetime.now(UTC),
            "returned_by": ctx.user_id,
            "fine": fine,
        }
        if fine:
            entry = fees.post_charge(
                loan["student_id"],
                head_code="LIBRARY",
                head_name="Library fine",
                amount=fine,
                by=ctx.user_id,
                session=session,
                reason=f"Library: {book.get('title', 'book')} returned {days_late} day(s) late",
                ref={"type": "loan", "id": loan["_id"]},
            )
            update["fine_entry_id"] = entry["_id"]
        db.loans.update_one({"_id": loan["_id"], "status": "open"}, {"$set": update}, session=session)
        held["r"] = _hold_or_shelve(copy, session)
        audit.record(
            "library.returned",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=loan["student_id"],
            ip=ip,
            details={"barcode": copy["barcode"], "days_late": days_late, "fine": fine},
            session=session,
        )

    run_in_transaction(work)
    _tell_ready(held.get("r"))
    returned = db.loans.find_one({"_id": loan["_id"]})
    assert returned is not None
    student = db.students.find_one({"_id": loan["student_id"]})
    out = loan_view(returned, book, student)
    out["held_for_reservation"] = bool(held.get("r"))
    return out


def renew(ctx: AuthContext, loan_id: str, *, own: bool) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {"_id": oid(loan_id, "Loan"), "status": "open"}
    if own:
        query["student_id"] = students.my_student(ctx)["_id"]
    loan = db.loans.find_one(query)
    if not loan:
        raise AppError(404, "Loan not found.")
    rules = settings()
    if loan.get("renewals", 0) >= rules["max_renewals"]:
        raise AppError(409, "This book can't be renewed again. Return it to the library.", "renew_limit")
    if loan["due_date"] < clock.today().isoformat():
        raise AppError(409, "An overdue book can't be renewed. Return it to the library.", "overdue")
    if db.book_reservations.find_one({"book_id": loan["book_id"], "status": "waiting"}):
        raise AppError(409, "Someone has reserved this book, so it can't be renewed.", "reserved")
    due = (date.fromisoformat(loan["due_date"]) + timedelta(days=rules["loan_days"])).isoformat()
    db.loans.update_one({"_id": loan["_id"]}, {"$set": {"due_date": due}, "$inc": {"renewals": 1}})
    audit.record(
        "library.renewed",
        actor_id=ctx.user_id,
        target_type="student",
        target_id=loan["student_id"],
        details={"due": due},
    )
    renewed = db.loans.find_one({"_id": loan["_id"]})
    assert renewed is not None
    return loan_view(renewed)


def mark_lost(ctx: AuthContext, loan_id: str, price: int, ip: str) -> dict[str, Any]:
    db = get_db()
    loan = db.loans.find_one({"_id": oid(loan_id, "Loan"), "status": "open"})
    if not loan:
        raise AppError(404, "Loan not found.")
    book = db.books.find_one({"_id": loan["book_id"]}, {"title": 1}) or {}

    def work(session: ClientSession) -> None:
        update: dict[str, Any] = {"status": "lost", "returned_at": datetime.now(UTC), "fine": price}
        if price:
            entry = fees.post_charge(
                loan["student_id"],
                head_code="LIBRARY",
                head_name="Library fine",
                amount=price,
                by=ctx.user_id,
                session=session,
                reason=f"Library: {book.get('title', 'book')} lost ({format_inr(price)})",
                ref={"type": "loan", "id": loan["_id"]},
            )
            update["fine_entry_id"] = entry["_id"]
        db.loans.update_one({"_id": loan["_id"]}, {"$set": update}, session=session)
        db.book_copies.update_one({"_id": loan["copy_id"]}, {"$set": {"status": "lost"}}, session=session)
        audit.record(
            "library.lost",
            actor_id=ctx.user_id,
            target_type="student",
            target_id=loan["student_id"],
            ip=ip,
            details={"barcode": loan["barcode"], "charged": price},
            session=session,
        )

    run_in_transaction(work)
    lost = db.loans.find_one({"_id": loan["_id"]})
    assert lost is not None
    return loan_view(lost)


def loans(*, status: str, q: str | None) -> list[dict[str, Any]]:
    """Open loans (status=open), overdue ones (status=overdue), or recent returns."""
    db = get_db()
    query: dict[str, Any] = (
        {"status": "open"} if status in ("open", "overdue") else {"status": {"$in": ["returned", "lost"]}}
    )
    if status == "overdue":
        query["due_date"] = {"$lt": clock.today().isoformat()}
    if q and q.strip():
        s = db.students.find_one({"prn": q.strip().upper()}, {"_id": 1})
        query["student_id"] = s["_id"] if s else None
    rows = list(
        db.loans.find(query)
        .sort("due_date" if status != "returned" else "returned_at", ASCENDING if status != "returned" else DESCENDING)
        .limit(300)
    )
    books = {
        b["_id"]: b
        for b in db.books.find({"_id": {"$in": list({r["book_id"] for r in rows})}}, {"title": 1, "authors": 1})
    }
    people = {
        s["_id"]: s
        for s in db.students.find({"_id": {"$in": list({r["student_id"] for r in rows})}}, {"name": 1, "prn": 1})
    }
    return [loan_view(r, books.get(r["book_id"]), people.get(r["student_id"])) for r in rows]


# --- reservations ---------------------------------------------------------------------------


def reserve(ctx: AuthContext, book_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    book = get_book(book_id)
    db = get_db()
    if db.book_copies.find_one({"book_id": book["_id"], "status": "available"}):
        raise AppError(409, "A copy is on the shelf: ask for it at the library counter.", "available")
    if db.loans.find_one({"book_id": book["_id"], "student_id": student["_id"], "status": "open"}):
        raise AppError(409, "You already have this book.", "conflict")
    if db.book_reservations.find_one(
        {"book_id": book["_id"], "student_id": student["_id"], "status": {"$in": list(OPEN_RESERVATION)}}
    ):
        raise AppError(409, "You have already reserved this book.", "conflict")
    if (
        db.book_reservations.count_documents({"student_id": student["_id"], "status": {"$in": list(OPEN_RESERVATION)}})
        >= 3
    ):
        raise AppError(409, "You can reserve 3 books at a time.", "limit")
    db.book_reservations.insert_one(
        {"book_id": book["_id"], "student_id": student["_id"], "status": "waiting", "created_at": datetime.now(UTC)}
    )
    return my_library(ctx)


def cancel_reservation(ctx: AuthContext, reservation_id: str) -> dict[str, Any]:
    student = students.my_student(ctx)
    db = get_db()
    r = db.book_reservations.find_one(
        {
            "_id": oid(reservation_id, "Reservation"),
            "student_id": student["_id"],
            "status": {"$in": list(OPEN_RESERVATION)},
        }
    )
    if not r:
        raise AppError(404, "Reservation not found.")
    held: dict[str, Any] = {}

    def work(session: ClientSession) -> None:
        db.book_reservations.update_one(
            {"_id": r["_id"]}, {"$set": {"status": "cancelled", "closed_at": datetime.now(UTC)}}, session=session
        )
        if r["status"] == "ready":
            copy = db.book_copies.find_one({"barcode": r.get("barcode")}, session=session)
            if copy and copy.get("held_for") == student["_id"]:
                held["r"] = _hold_or_shelve(copy, session)

    run_in_transaction(work)
    _tell_ready(held.get("r"))
    return my_library(ctx)


def my_library(ctx: AuthContext) -> dict[str, Any]:
    student = students.my_student(ctx)
    db = get_db()
    rows = list(db.loans.find({"student_id": student["_id"]}).sort("issued_at", DESCENDING).limit(20))
    books = {
        b["_id"]: b for b in db.books.find({"_id": {"$in": [r["book_id"] for r in rows]}}, {"title": 1, "authors": 1})
    }
    res = list(
        db.book_reservations.find({"student_id": student["_id"], "status": {"$in": list(OPEN_RESERVATION)}}).sort(
            "created_at", ASCENDING
        )
    )
    rbooks = {b["_id"]: b for b in db.books.find({"_id": {"$in": [r["book_id"] for r in res]}}, {"title": 1})}
    rules = settings()
    return {
        "rules": {k: rules[k] for k in ("loan_days", "max_books", "fine_per_day", "max_renewals")},
        "loans": [loan_view(r, books.get(r["book_id"])) for r in rows if r["status"] == "open"],
        "history": [loan_view(r, books.get(r["book_id"])) for r in rows if r["status"] != "open"][:10],
        "reservations": [
            {
                "id": str(r["_id"]),
                "book_id": str(r["book_id"]),
                "title": rbooks.get(r["book_id"], {}).get("title"),
                "status": r["status"],
                "ready_until": r.get("ready_until"),
                "position": db.book_reservations.count_documents(
                    {"book_id": r["book_id"], "status": "waiting", "created_at": {"$lte": r["created_at"]}}
                ),
            }
            for r in res
        ],
    }


# --- daily job and dues ---------------------------------------------------------------------


def daily(today: date | None = None) -> dict[str, int]:
    """Overdue reminders (the day after the due date, then weekly) and lapsed holds."""
    from app.modules.messaging import service as messaging

    db = get_db()
    today = today or clock.today()
    reminded = 0
    for loan in db.loans.find({"status": "open", "due_date": {"$lt": today.isoformat()}}).limit(500):
        late = (today - date.fromisoformat(loan["due_date"])).days
        if late == 1 or late % 7 == 0:
            book = db.books.find_one({"_id": loan["book_id"]}, {"title": 1}) or {}
            messaging.queue(
                loan["student_id"],
                "library_overdue",
                {"title": book.get("title", "book"), "date": date.fromisoformat(loan["due_date"]).strftime("%d %b")},
            )
            reminded += 1
    lapsed = 0
    for r in db.book_reservations.find({"status": "ready", "ready_until": {"$lt": today.isoformat()}}).limit(200):
        nxt: dict[str, Any] = {}

        def work(session: ClientSession, r: dict[str, Any] = r, nxt: dict[str, Any] = nxt) -> None:
            db.book_reservations.update_one(
                {"_id": r["_id"]}, {"$set": {"status": "expired", "closed_at": datetime.now(UTC)}}, session=session
            )
            copy = db.book_copies.find_one({"barcode": r.get("barcode"), "status": "held"}, session=session)
            if copy:
                nxt["r"] = _hold_or_shelve(copy, session)

        run_in_transaction(work)
        _tell_ready(nxt.get("r"))
        lapsed += 1
    return {"overdue_reminders": reminded, "holds_lapsed": lapsed}


def dues(student_id: ObjectId) -> list[dict[str, Any]]:
    """Books a student still has (for the no-dues check)."""
    return [loan_view(lo) for lo in get_db().loans.find({"student_id": student_id, "status": "open"})]


def overview() -> dict[str, Any]:
    db = get_db()
    today = clock.today().isoformat()
    return {
        "titles": db.books.count_documents({}),
        "copies": db.book_copies.count_documents({"status": {"$nin": ["withdrawn", "lost"]}}),
        "issued": db.loans.count_documents({"status": "open"}),
        "overdue": db.loans.count_documents({"status": "open", "due_date": {"$lt": today}}),
        "reservations": db.book_reservations.count_documents({"status": {"$in": list(OPEN_RESERVATION)}}),
        "settings": settings(),
    }
