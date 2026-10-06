from datetime import date, timedelta

from bson import ObjectId

from app.core import email
from app.modules.library import service as library
from app.modules.messaging import service as messaging
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"
DAY = date(2026, 10, 5)


def _setup(client, sign_in, db, fees):  # noqa: F811
    lib = new_client(client)
    sign_in(lib, ["librarian"])
    book = lib.post(
        f"{API}/library/books",
        json={"isbn": "978-0-13-468599-1", "title": "Clean Code", "authors": ["Robert C. Martin"], "copies": 2},
    ).json()
    assert [c["barcode"] for c in book["copy_list"]] == ["LIB000001", "LIB000002"] and book["available"] == 2
    students = {}
    for prn in ("2026BCA001", "2026BCA002", "2026BCA003"):
        db.students.update_one({"prn": prn}, {"$set": {"email": f"{prn.lower()}@example.com"}})
        c = new_client(client)
        sign_in_as_student(c, db, prn)
        students[prn] = c
    return lib, book, students


def test_issue_return_fine_and_reservation(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 11))
    lib, book, st = _setup(client, sign_in, db, fees)
    first = lib.post(f"{API}/library/issue", json={"barcode": "lib000001", "prn": "2026bca001"}).json()
    assert first["due_date"] == (DAY + timedelta(days=14)).isoformat() and first["student"]["name"] == "Rohan Patil"
    assert (
        lib.post(f"{API}/library/issue", json={"barcode": "LIB000001", "prn": "2026BCA002"}).json()["error"]["code"]
        == "not_available"
    )
    assert (
        st["2026BCA001"].post(f"{API}/library/issue", json={"barcode": "LIB000002", "prn": "2026BCA001"}).status_code
        == 403
    )

    # One copy left on the shelf: no reservation yet; once both are out, Om reserves.
    assert (
        st["2026BCA003"].post(f"{API}/me/library/reservations", json={"book_id": book["id"]}).json()["error"]["code"]
        == "available"
    )
    lib.post(f"{API}/library/issue", json={"barcode": "LIB000002", "prn": "2026BCA002"})
    mine = st["2026BCA003"].post(f"{API}/me/library/reservations", json={"book_id": book["id"]}).json()
    assert mine["reservations"][0]["position"] == 1
    assert st["2026BCA002"].post(f"{API}/me/library/loans/{mine['reservations'][0]['id']}/renew").status_code == 404
    neha_loan = st["2026BCA002"].get(f"{API}/me/library").json()["loans"][0]
    assert (
        st["2026BCA002"].post(f"{API}/me/library/loans/{neha_loan['id']}/renew").json()["error"]["code"] == "reserved"
    )

    # Neha returns 6 days late: ₹2 a day goes into her fees, and the copy is kept for Om.
    at(monkeypatch, ist(DAY + timedelta(days=20), 11))
    email.OUTBOX.clear()
    back = lib.post(f"{API}/library/return", json={"barcode": "LIB000002"}).json()
    assert back["fine"] == 1_200 and back["held_for_reservation"]
    charge = db.ledger_entries.find_one({"type": "charge", "student_id": ObjectId(fees["students"]["2026BCA002"])})
    assert charge["amount"] == 1_200 and "6 day(s) late" in charge["reason"]
    assert db.fee_heads.find_one({"_id": charge["lines"][0]["head_id"]})["code"] == "LIBRARY"
    assert "Clean Code" in email.OUTBOX[-1].text and email.OUTBOX[-1].to == "2026bca003@example.com"
    assert lib.post(f"{API}/library/issue", json={"barcode": "LIB000002", "prn": "2026BCA001"}).json()["error"][
        "code"
    ] in ("held", "overdue")
    om = lib.post(f"{API}/library/issue", json={"barcode": "LIB000002", "prn": "2026BCA003"}).json()
    assert om["student"]["prn"] == "2026BCA003"
    assert st["2026BCA003"].get(f"{API}/me/library").json()["reservations"] == []

    # Rohan is overdue now: reminders are queued, and he can't borrow more until he returns.
    db.message_queue.delete_many({})
    assert library.daily(DAY + timedelta(days=21))["overdue_reminders"] == 1  # 7 days late
    assert db.message_queue.find_one({})["template"] == "library_overdue"
    messaging.process_queue()
    overdue = lib.get(f"{API}/library/loans", params={"status": "overdue"}).json()
    assert [(x["student"]["prn"], x["days_late"]) for x in overdue] == [("2026BCA001", 6)]
    lost = lib.post(f"{API}/library/loans/{overdue[0]['id']}/lost", json={"price": 45_000}).json()
    assert lost["status"] == "lost"
    assert db.book_copies.find_one({"barcode": "LIB000001"})["status"] == "lost"
    assert lib.get(f"{API}/library/overview").json()["copies"] == 1


def test_catalogue_search_isbn_and_limits(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 11))
    lib, book, st = _setup(client, sign_in, db, fees)

    class Res:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ISBN:9780132350884": {
                    "title": "Clean Code",
                    "authors": [{"name": "Robert C. Martin"}],
                    "publishers": [{"name": "Prentice Hall"}],
                    "publish_date": "2008",
                }
            }

    monkeypatch.setattr(library.httpx, "get", lambda *a, **k: Res())
    found = lib.get(f"{API}/library/isbn/978-0132350884").json()
    assert found["found"] and found["year"] == 2008 and found["publisher"] == "Prentice Hall"

    seen = st["2026BCA001"].get(f"{API}/library/books", params={"q": "martin"}).json()
    assert [b["title"] for b in seen] == ["Clean Code"] and "copy_list" not in seen[0]
    lib.put(
        f"{API}/library/settings",
        json={"loan_days": 7, "max_books": 1, "fine_per_day": 100, "max_renewals": 1, "hold_days": 2},
    )
    lib.post(f"{API}/library/issue", json={"barcode": "LIB000001", "prn": "2026BCA001"})
    assert (
        lib.post(f"{API}/library/issue", json={"barcode": "LIB000002", "prn": "2026BCA001"}).json()["error"]["code"]
        == "limit"
    )
    loan = st["2026BCA001"].get(f"{API}/me/library").json()["loans"][0]
    renewed = st["2026BCA001"].post(f"{API}/me/library/loans/{loan['id']}/renew").json()
    assert renewed["due_date"] == (DAY + timedelta(days=14)).isoformat()
    assert st["2026BCA001"].post(f"{API}/me/library/loans/{loan['id']}/renew").json()["error"]["code"] == "renew_limit"
    # Returned on time: no fine.
    assert lib.post(f"{API}/library/return", json={"barcode": "LIB000001"}).json()["fine"] == 0
    assert db.ledger_entries.count_documents({"type": "charge"}) == 0
