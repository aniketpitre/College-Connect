from datetime import UTC, date, datetime

from bson import ObjectId

from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"


def test_overdue_book_and_hostel_bed_block_a_tc_until_cleared(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    """Plan 7.3: an overdue library book appears in the no-dues check and blocks a TC until cleared."""
    at(monkeypatch, ist(date(2026, 9, 1), 11))
    lib, warden, office, accounts = (new_client(client) for _ in range(4))
    sign_in(lib, ["librarian"])
    sign_in(warden, ["warden"])
    sign_in(office, ["office"])
    sign_in(accounts, ["accounts"])
    lib.post(f"{API}/library/books", json={"title": "Let Us C", "authors": ["Kanetkar"], "copies": 1})
    lib.post(f"{API}/library/issue", json={"barcode": "LIB000001", "prn": "2026BCA003"})
    block = warden.post(f"{API}/hostel/blocks", json={"name": "Raigad", "annual_fee": 0}).json()["blocks"][0]
    room = warden.post(f"{API}/hostel/blocks/{block['id']}/rooms", json={"numbers": ["1"]}).json()["blocks"][0]
    warden.post(f"{API}/hostel/allotments", json={"prn": "2026BCA003", "room_id": room["rooms"][0]["id"]})

    at(monkeypatch, ist(date(2026, 10, 5), 11))
    om = new_client(client)
    sign_in_as_student(om, db, "2026BCA003")
    sid = ObjectId(fees["students"]["2026BCA003"])
    owed = om.get(f"{API}/me/certificates").json()["no_dues"]
    assert [d["area"] for d in owed] == ["library", "hostel"] and owed[0]["title"] == "Let Us C"
    check = accounts.get(f"{API}/certificates/no-dues", params={"prn": "2026bca003"}).json()
    assert check["clear"] is False and len(check["dues"]) == 2
    assert lib.get(f"{API}/certificates/no-dues", params={"prn": "2026BCA003"}).status_code == 403

    rid = om.post(
        f"{API}/me/certificates",
        json={"type": "tc", "purpose": "Admission elsewhere", "reason_for_leaving": "Moving to Pune"},
    ).json()["id"]

    def verify():
        return office.post(f"{API}/certificates/requests/{rid}/action", json={"action": "verify"})

    blocked = verify().json()["error"]
    assert blocked["code"] == "dues_pending"
    assert "1 library book(s) to return" in blocked["message"] and "hostel bed" in blocked["message"]

    # Returning the late book adds its fine to the fee account: the TC is now blocked by fees.
    lib.post(f"{API}/library/return", json={"barcode": "LIB000001"})
    hostel = warden.get(f"{API}/hostel").json()["blocks"][0]["rooms"][0]["occupants"][0]
    warden.post(f"{API}/hostel/allotments/{hostel['allotment_id']}/vacate", json={"reason": "Leaving college"})
    owed = om.get(f"{API}/me/certificates").json()["no_dues"]
    assert [d["area"] for d in owed] == ["fees"] and owed[0]["amount"] == 20 * 200  # 20 days late
    assert "fees of Rs. 40.00" in verify().json()["error"]["message"]

    fine = db.ledger_entries.find_one({"student_id": sid, "type": "charge"})
    db.ledger_entries.insert_one(
        {"student_id": sid, "academic_year_id": fine["academic_year_id"], "type": "payment", "amount": -fine["amount"],
         "lines": [{**fine["lines"][0], "amount": -fine["amount"]}], "at": datetime.now(UTC), "created_by": None}
    )  # fmt: skip
    assert accounts.get(f"{API}/certificates/no-dues", params={"prn": "2026BCA003"}).json()["clear"] is True
    assert verify().json()["status"] == "verified"
