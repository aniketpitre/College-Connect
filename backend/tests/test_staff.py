from datetime import UTC, date, datetime

from app.core import email
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist

API = "/api/v1"
DAY = date(2026, 10, 5)  # a Monday


def test_staff_records_leave_balances_approvals_and_workload(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 10))
    cs = db.departments.find_one({"code": "CS"})["_id"]
    other = db.departments.insert_one({"code": "COM", "name": "Commerce", "status": "active"}).inserted_id
    office, principal, hod, hod2, teacher = (new_client(client) for _ in range(5))
    sign_in(office, ["office"])
    sign_in(principal, ["principal"])
    h_user = sign_in(hod, ["hod"], name="Dr. Sunita Rane")
    sign_in(hod2, ["hod"], name="Dr. Kulkarni")
    t_user = sign_in(teacher, ["faculty"], name="Amit Deshmukh")
    db.users.update_many({"_id": {"$in": [h_user["_id"], t_user["_id"]]}}, {"$set": {"department_id": cs}})
    db.users.update_one({"roles": "hod", "name": "Dr. Kulkarni"}, {"$set": {"department_id": other}})
    db.holidays.insert_one({"date": "2026-10-20", "name": "Dussehra"})
    db.timetable_slots.insert_one(
        {
            "timetable_id": None,
            "division_id": None,
            "day": 3,
            "start": "09:00",
            "end": "10:00",
            "subject_id": None,
            "faculty_ids": [t_user["_id"]],
            "room": "101",
            "valid_from": "2026-06-01",
            "valid_to": "2026-11-30",
            "status": "active",
            "created_at": datetime.now(UTC),
        }
    )

    # Staff records: the office keeps qualifications; the NAAC summary counts Ph.D. and NET/SET.
    body = {
        "employee_code": "t-014",
        "designation": "Assistant Professor",
        "employment": "permanent",
        "qualifications": [
            {"level": "pg", "degree": "M.Sc. Computer Science", "university": "SPPU", "year": 2012},
            {"level": "net", "degree": "UGC NET", "year": 2013},
            {"level": "phd", "degree": "Ph.D. Computer Science", "university": "SPPU", "year": 2019},
        ],
    }
    saved = office.put(f"{API}/staff/{t_user['_id']}", json=body).json()
    assert saved["employee_code"] == "T-014" and saved["phd"] and saved["net_set"]
    assert office.put(f"{API}/staff/{h_user['_id']}", json=body).json()["error"]["code"] == "conflict"
    summary = principal.get(f"{API}/staff/summary").json()
    assert summary["phd"] == 1 and summary["net_set"] == 1 and summary["teaching"] == 4
    assert {r["name"] for r in hod.get(f"{API}/staff").json()} == {"Dr. Sunita Rane", "Amit Deshmukh"}
    assert teacher.get(f"{API}/staff").status_code == 403
    assert teacher.get(f"{API}/staff/me").json()["designation"] == "Assistant Professor"

    # Amit asks for casual leave Tue 20 – Wed 21 Oct; the 20th is a holiday, so 1 day. His HOD is told.
    db.users.update_one({"_id": h_user["_id"]}, {"$set": {"email": "hod@college.test"}})
    db.users.update_one({"_id": t_user["_id"]}, {"$set": {"email": "amit@college.test"}})
    email.OUTBOX.clear()
    leave = {"code": "CL", "from_date": "2026-10-20", "to_date": "2026-10-21", "reason": "Family function"}
    r = teacher.post(f"{API}/me/leave", json=leave).json()
    assert r["days"] == 1 and r["status"] == "pending" and r["approver"] == "hod"
    assert [m.to for m in email.OUTBOX] == ["hod@college.test"]
    assert teacher.post(f"{API}/me/leave", json=leave).json()["error"]["code"] == "conflict"
    too_long = {"code": "CL", "from_date": "2026-11-02", "to_date": "2026-11-12", "reason": "Trip"}
    assert teacher.post(f"{API}/me/leave", json=too_long).json()["error"]["code"] == "no_balance"
    half = {"code": "ML", "from_date": "2026-11-02", "to_date": "2026-11-02", "half_day": True, "reason": "Doctor"}
    assert teacher.post(f"{API}/me/leave", json=half).json()["error"]["field"] == "half_day"
    cl = next(b for b in teacher.get(f"{API}/me/leave").json()["balances"] if b["code"] == "CL")
    assert (cl["allowance"], cl["pending"], cl["available"]) == (8, 1, 7)

    # The HOD sees the lecture Amit would miss; the other department's HOD doesn't see the request.
    pending = hod.get(f"{API}/leave/requests").json()
    assert len(pending) == 1 and [x["date"] for x in pending[0]["lectures"]] == ["2026-10-21"]
    assert hod2.get(f"{API}/leave/requests").json() == []
    assert hod2.post(f"{API}/leave/requests/{r['id']}/decide", json={"approve": True}).status_code == 404
    assert hod.post(f"{API}/leave/requests/{r['id']}/decide", json={"approve": False}).status_code == 422
    email.OUTBOX.clear()
    done = hod.post(f"{API}/leave/requests/{r['id']}/decide", json={"approve": True}).json()
    assert done["status"] == "approved" and [m.to for m in email.OUTBOX] == ["amit@college.test"]
    cl = next(b for b in teacher.get(f"{API}/me/leave").json()["balances"] if b["code"] == "CL")
    assert (cl["taken"], cl["available"]) == (1, 7)

    # The HOD's own leave goes to the Principal; the Principal's own is recorded as approved.
    own = hod.post(f"{API}/me/leave", json={**leave, "code": "EL", "reason": "Conference"}).json()
    assert own["approver"] == "principal" and hod.get(f"{API}/leave/requests").json() == []
    assert principal.post(f"{API}/leave/requests/{own['id']}/decide", json={"approve": True}).status_code == 200
    trip = {"code": "CL", "from_date": "2026-11-02", "to_date": "2026-11-02", "reason": "Meeting in Mumbai"}
    mine = principal.post(f"{API}/me/leave", json=trip).json()
    assert mine["status"] == "approved" and mine["approver"] == "self"

    # Office adds carried-forward earned leave; Amit cancels leave that hasn't started.
    office.post(
        f"{API}/leave/adjustments",
        json={"user_id": str(t_user["_id"]), "code": "EL", "days": 2, "reason": "Carried forward"},
    )
    el = next(b for b in teacher.get(f"{API}/me/leave").json()["balances"] if b["code"] == "EL")
    assert el["allowance"] == 17
    assert teacher.post(f"{API}/me/leave/{r['id']}/cancel").json()["balances"][0]["taken"] == 0

    # Workload from the timetable in force today, and who is on leave today.
    at(monkeypatch, ist(date(2026, 10, 21), 9))
    load = principal.get(f"{API}/staff/workload").json()
    amit = next(w for w in load["staff"] if w["name"] == "Amit Deshmukh")
    assert (amit["lectures"], amit["hours"], amit["leave_taken"]) == (1, 1.0, 0)
    assert load["on_leave_today"] == ["Dr. Sunita Rane"]
    assert teacher.get(f"{API}/staff/workload").status_code == 403
