from datetime import UTC, datetime, timedelta

import pytest

from app.core import clock
from tests.academics_fixtures import API, MONDAY, academics, college, make_timetable, slot  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_students import sign_in_as_student


def at(monkeypatch, when: datetime) -> None:
    """Freeze the college clock (IST) at `when`."""
    monkeypatch.setattr(clock, "now", lambda: when.astimezone(UTC))
    monkeypatch.setattr(clock, "today", lambda: when.astimezone(clock.IST).date())


def ist(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=clock.IST)


@pytest.fixture
def week(academics):  # noqa: F811
    office = academics["office"]
    s, t = academics["subjects"], academics["teachers"]
    tt = make_timetable(office, academics)
    url = f"{API}/timetables/{tt['id']}/slots"
    c = office.post(url, json=slot(s["BCA101"], [t["rao"]["id"]], day=1)).json()
    maths = office.post(url, json=slot(s["BCA102"], [t["khan"]["id"]], day=1, start="10:00", end="11:00")).json()
    lab = office.post(
        url, json=slot(s["BCA103"], [t["khan"]["id"]], day=2, start="11:00", end="13:00", batch="B1")
    ).json()
    return {**academics, "c": c["id"], "maths": maths["id"], "lab": lab["id"]}


def sheet(client, slot_id, day=MONDAY):
    return client.get(f"{API}/attendance/sheet", params={"slot_id": slot_id, "day": day.isoformat()})


def save(client, slot_id, absent, day=MONDAY, **extra):
    return client.put(
        f"{API}/attendance/sheet", json={"slot_id": slot_id, "date": day.isoformat(), "absent": absent, **extra}
    )


def test_teacher_marks_attendance_in_one_save(monkeypatch, week, db):
    at(monkeypatch, ist(MONDAY, 9, 50))
    rao = week["teachers"]["rao"]["client"]
    db.students.update_one({"prn": "2026BCA003"}, {"$set": {"roll_no": "1"}})
    today = rao.get(f"{API}/attendance/today").json()
    assert [x["subject_code"] for x in today["lectures"]] == ["BCA101"]
    assert today["lectures"][0]["takeable"] and today["lectures"][0]["session"] is None

    s = sheet(rao, week["c"]).json()
    assert [x["prn"] for x in s["students"]][0] == "2026BCA003"  # roll no. order
    assert s["can_save"] and s["session"] is None
    neha = week["students"]["2026BCA002"]
    first = save(rao, week["c"], [neha], client_id="dev-1")
    assert first.status_code == 200 and first.json()["present"] == 2 and first.json()["version"] == 1
    # The same offline save arriving again changes nothing.
    again = save(rao, week["c"], [neha], client_id="dev-1")
    assert again.status_code == 200 and again.json()["version"] == 1

    # A second device that hadn't seen version 1 gets a conflict, not a silent overwrite.
    conflict = save(rao, week["c"], [], client_id="dev-2")
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "attendance_conflict"
    fixed = save(rao, week["c"], [], base_version=1)
    assert fixed.json()["version"] == 2 and fixed.json()["present"] == 3
    assert save(rao, week["c"], ["64b7f0000000000000000000"], base_version=2).status_code == 422

    after = rao.get(f"{API}/attendance/today").json()["lectures"][0]["session"]
    assert after == {"present": 3, "total": 3}
    assert db.audit_log.count_documents({"action": {"$in": ["attendance.marked", "attendance.changed"]}}) == 2
    # Not for tomorrow, and not someone else's lecture.
    assert save(rao, week["c"], [], day=MONDAY + timedelta(days=7)).status_code == 422
    assert save(week["teachers"]["khan"]["client"], week["c"], []).status_code == 403


def test_substitute_and_cancelled_lectures(monkeypatch, week):
    at(monkeypatch, ist(MONDAY, 12))
    office, t = week["office"], week["teachers"]
    office.post(
        f"{API}/timetable-slots/{week['maths']}/changes",
        json={"date": MONDAY.isoformat(), "kind": "substitute", "faculty_ids": [t["rao"]["id"]], "reason": "Leave"},
    )
    office.post(
        f"{API}/timetable-slots/{week['c']}/changes",
        json={"date": MONDAY.isoformat(), "kind": "cancelled", "reason": "Exam duty"},
    )
    rao, khan = t["rao"]["client"], t["khan"]["client"]
    lectures = {x["subject_code"]: x for x in rao.get(f"{API}/attendance/today").json()["lectures"]}
    assert lectures["BCA102"]["takeable"] and not lectures["BCA101"]["takeable"]
    assert save(rao, week["maths"], []).status_code == 200
    assert save(khan, week["maths"], [], base_version=1).status_code == 403  # handed over today
    cancelled = save(rao, week["c"], [])
    assert cancelled.status_code == 409 and cancelled.json()["error"]["code"] == "cancelled"


def test_after_48_hours_the_hod_decides(monkeypatch, week, db):
    at(monkeypatch, ist(MONDAY, 9, 55))
    t = week["teachers"]
    rao, hod, comhod = t["rao"]["client"], t["hod"]["client"], t["comhod"]["client"]
    neha, om = week["students"]["2026BCA002"], week["students"]["2026BCA003"]
    save(rao, week["c"], [neha])

    at(monkeypatch, ist(MONDAY + timedelta(days=2), 10, 1))  # 48 h after 10:00 Monday
    closed = save(rao, week["c"], [neha, om], base_version=1)
    assert closed.status_code == 403 and closed.json()["error"]["code"] == "edit_window_closed"
    s = sheet(rao, week["c"]).json()
    assert not s["can_save"] and s["can_request_edit"]

    req = rao.post(
        f"{API}/attendance/edit-requests",
        json={
            "slot_id": week["c"],
            "date": MONDAY.isoformat(),
            "absent": [neha, om],
            "reason": "Om left after roll call",
        },
    )
    assert req.status_code == 201 and req.json()["absent_now"] == 1 and req.json()["absent_new"] == 2
    dup = rao.post(
        f"{API}/attendance/edit-requests",
        json={"slot_id": week["c"], "date": MONDAY.isoformat(), "absent": [], "reason": "Second try"},
    )
    assert dup.status_code == 409
    assert [r["id"] for r in rao.get(f"{API}/attendance/edit-requests").json()] == [req.json()["id"]]
    assert comhod.get(f"{API}/attendance/edit-requests", params={"status": "pending"}).json() == []
    assert (
        comhod.post(f"{API}/attendance/edit-requests/{req.json()['id']}/decide", json={"approve": True}).status_code
        == 403
    )
    assert (
        rao.post(f"{API}/attendance/edit-requests/{req.json()['id']}/decide", json={"approve": True}).status_code == 403
    )

    pending = hod.get(f"{API}/attendance/edit-requests", params={"status": "pending"}).json()
    assert pending[0]["class"] == "BCA FY A" and pending[0]["requested_by"] == "Anita Rao"
    done = hod.post(f"{API}/attendance/edit-requests/{req.json()['id']}/decide", json={"approve": True})
    assert done.status_code == 200 and done.json()["status"] == "approved"
    record = db.attendance_sessions.find_one({})
    assert len(record["absent"]) == 2 and record["version"] == 2 and record["history"][0]["via"] == "hod_approved"
    # The HOD may also change it directly (audited).
    direct = save(hod, week["c"], [], base_version=2)
    assert direct.status_code == 200 and direct.json()["present"] == 3


def test_practical_batch_roster_and_exemptions(monkeypatch, week, db, client, sign_in):
    tuesday = MONDAY + timedelta(days=1)
    at(monkeypatch, ist(tuesday, 13, 5))
    office, khan = week["office"], week["teachers"]["khan"]["client"]
    # No batches set yet: the whole class. Then only batch B1.
    assert len(sheet(khan, week["lab"], tuesday).json()["students"]) == 3
    for prn, batch in (("2026BCA001", "B1"), ("2026BCA002", "B2"), ("2026BCA003", "b1")):
        r = office.patch(f"{API}/students/{week['students'][prn]}", json={"batch": batch})
        assert r.status_code == 200, r.text
    assert [x["prn"] for x in sheet(khan, week["lab"], tuesday).json()["students"]] == ["2026BCA003", "2026BCA001"]

    rohan = week["students"]["2026BCA001"]
    ex = office.post(
        f"{API}/attendance/exemptions",
        json={"student_id": rohan, "kind": "medical", "from_date": MONDAY.isoformat(),
              "to_date": tuesday.isoformat(), "reason": "Fever, doctor's note"},
    )  # fmt: skip
    assert ex.status_code == 201 and ex.json()["kind_label"] == "Medical"
    students = sheet(khan, week["lab"], tuesday).json()["students"]
    assert {x["prn"]: x["exempt"] for x in students} == {"2026BCA001": "medical", "2026BCA003": None}
    assert (
        office.get(f"{API}/attendance/exemptions", params={"student_id": rohan}).json()[0]["student"] == "Rohan Patil"
    )
    assert office.post(f"{API}/attendance/exemptions/{ex.json()['id']}/cancel", json={}).status_code == 422
    assert (
        office.post(f"{API}/attendance/exemptions/{ex.json()['id']}/cancel", json={"reason": "Wrong dates"}).status_code
        == 204
    )
    sign_in(client, ["accounts"])
    assert client.get(f"{API}/attendance/exemptions").status_code == 403
    assert khan.post(f"{API}/attendance/exemptions", json={}).status_code == 403

    # Students can't reach attendance staff routes.
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert sheet(student, week["lab"], tuesday).status_code == 403
    assert save(student, week["lab"], [], day=tuesday).status_code == 403
