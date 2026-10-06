from datetime import UTC, date, datetime

from bson import ObjectId

from app.core import email
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"
DAY = date(2026, 10, 5)


def test_rooms_allotment_fee_outpass_complaints(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 10))
    warden = new_client(client)
    sign_in(warden, ["warden"])
    block = warden.post(
        f"{API}/hostel/blocks", json={"name": "Shivneri", "gender": "any", "annual_fee": 30_000 * 100}
    ).json()["blocks"][0]
    rooms = warden.post(f"{API}/hostel/blocks/{block['id']}/rooms", json={"numbers": ["101", "102"], "beds": 2}).json()[
        "blocks"
    ][0]["rooms"]
    r101, r102 = rooms[0]["id"], rooms[1]["id"]
    for prn in ("2026BCA001", "2026BCA002"):
        assert warden.post(f"{API}/hostel/allotments", json={"prn": prn, "room_id": r101}).status_code == 200
    assert (
        warden.post(f"{API}/hostel/allotments", json={"prn": "2026BCA003", "room_id": r101}).json()["error"]["code"]
        == "full"
    )
    assert (
        warden.post(f"{API}/hostel/allotments", json={"prn": "2026BCA001", "room_id": r102}).status_code == 409
    )  # one bed each
    fee = db.ledger_entries.find_one({"type": "charge", "student_id": ObjectId(fees["students"]["2026BCA001"])})
    assert fee["amount"] == 3_000_000 and fee["reason"] == "Hostel Shivneri 2026-27"

    # Neha moves rooms within the year: no second hostel fee.
    view = warden.get(f"{API}/hostel").json()["blocks"][0]
    neha = next(o for o in view["rooms"][0]["occupants"] if o["prn"] == "2026BCA002")
    warden.post(f"{API}/hostel/allotments/{neha['allotment_id']}/vacate", json={"reason": "Room change"})
    warden.post(f"{API}/hostel/allotments", json={"prn": "2026BCA002", "room_id": r102})
    assert (
        db.ledger_entries.count_documents({"type": "charge", "student_id": ObjectId(fees["students"]["2026BCA002"])})
        == 1
    )
    assert warden.get(f"{API}/hostel").json()["blocks"][0]["occupied"] == 2

    # Out-pass: Rohan asks, the warden approves, Rohan and his father are told; he comes back late.
    rohan, om = new_client(client), new_client(client)
    sign_in_as_student(rohan, db, "2026BCA001")
    sign_in_as_student(om, db, "2026BCA003")
    sid = ObjectId(fees["students"]["2026BCA001"])
    db.students.update_one({"_id": sid}, {"$set": {"email": "rohan@example.com"}})
    db.users.insert_one(
        {"kind": "parent", "name": "Suresh Patil", "roles": ["parent"], "status": "active", "phone": "9876500001",
         "contact_email": "suresh@example.com", "children": [{"student_id": sid, "relation": "Father"}],
         "created_at": datetime.now(UTC)}
    )  # fmt: skip
    body = {
        "leave_at": "2026-10-10T09:00:00+05:30",
        "return_by": "2026-10-11T18:00:00+05:30",
        "destination": "Home, Satara",
        "reason": "Family function",
    }
    assert rohan.post(f"{API}/me/hostel/outpasses", json=body).status_code == 201
    assert rohan.post(f"{API}/me/hostel/outpasses", json=body).json()["error"]["code"] == "conflict"
    assert om.post(f"{API}/me/hostel/outpasses", json=body).json()["error"]["code"] == "not_resident"
    pending = warden.get(f"{API}/hostel/outpasses").json()
    assert [p["student"]["prn"] for p in pending] == ["2026BCA001"]
    email.OUTBOX.clear()
    warden.post(f"{API}/hostel/outpasses/{pending[0]['id']}/action", json={"action": "approve"})
    assert {m.to for m in email.OUTBOX} == {"rohan@example.com", "suresh@example.com"}
    assert "Home, Satara" in email.OUTBOX[0].text
    warden.post(f"{API}/hostel/outpasses/{pending[0]['id']}/action", json={"action": "out"})
    at(monkeypatch, ist(date(2026, 10, 12), 9))
    back = warden.post(f"{API}/hostel/outpasses/{pending[0]['id']}/action", json={"action": "returned"}).json()
    assert back["status"] == "returned" and back["late"] is True

    # Complaint and mess menu.
    rohan.post(f"{API}/me/hostel/complaints", json={"category": "water", "text": "No hot water on the first floor"})
    c = warden.get(f"{API}/hostel/complaints").json()[0]
    assert c["room"] == "Shivneri 101" and c["student"]["prn"] == "2026BCA001"
    warden.patch(f"{API}/hostel/complaints/{c['id']}", json={"status": "resolved", "note": "Geyser repaired"})
    warden.put(f"{API}/hostel/mess-menu", json={"days": {"mon": "Poha, dal-rice, chapati-bhaji"}})
    mine = rohan.get(f"{API}/me/hostel").json()
    assert mine["allotment"]["room"] == "101" and mine["complaints"][0]["status"] == "resolved"
    assert mine["mess_menu"]["mon"].startswith("Poha") and mine["outpasses"][0]["late"]
    assert om.get(f"{API}/me/hostel").json() == {
        "resident": False,
        "allotment": None,
        "outpasses": [],
        "complaints": [],
        "mess_menu": None,
    }
    assert rohan.get(f"{API}/hostel").status_code == 403
