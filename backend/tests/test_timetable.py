from tests.academics_fixtures import API, MONDAY, academics, college, make_timetable, slot  # noqa: F401
from tests.test_students import sign_in_as_student


def test_office_builds_a_timetable_and_clashes_are_refused(client, academics, db):  # noqa: F811
    office = academics["office"]
    s, t = academics["subjects"], academics["teachers"]
    tt = make_timetable(office, academics)
    assert tt["semester"] == 1 and tt["division"] == "BCA FY A" and tt["can_manage"]
    url = f"{API}/timetables/{tt['id']}/slots"

    first = office.post(url, json=slot(s["BCA101"], [t["rao"]["id"]], room="101"))
    assert first.status_code == 201 and first.json()["faculty"] == ["Anita Rao"]
    # Only subjects of this semester.
    bad = office.post(url, json=slot(s["BCA301"], [t["khan"]["id"]], day=2))
    assert bad.status_code == 422 and bad.json()["error"]["field"] == "subject_id"
    # Same division, overlapping time.
    clash = office.post(url, json=slot(s["BCA102"], [t["khan"]["id"]], start="09:30", end="10:30"))
    assert clash.status_code == 409 and clash.json()["error"]["field"] == "start"
    # Two practical batches in parallel are fine; the same batch twice is not.
    lab = slot(s["BCA103"], [t["khan"]["id"]], day=3, start="11:00", end="13:00", room="LAB1", batch="b1")
    assert office.post(url, json=lab).status_code == 201
    lab2 = slot(s["BCA103"], [t["hod"]["id"]], day=3, start="11:00", end="13:00", room="LAB2", batch="B2")
    assert office.post(url, json=lab2).status_code == 201
    lab3 = {**lab2, "room": "LAB3", "faculty_ids": [academics["teachers"]["rao"]["id"]], "batch": "B1"}
    assert office.post(url, json=lab3).json()["error"]["field"] == "start"

    # Another division: the same teacher or room at the same time clashes.
    sy = make_timetable(office, academics, division=academics["div"][2], term=1)
    assert sy["semester"] == 3
    sy_url = f"{API}/timetables/{sy['id']}/slots"
    r = office.post(sy_url, json=slot(s["BCA301"], [t["rao"]["id"]], start="09:30", end="10:30"))
    assert r.status_code == 409 and "Anita Rao" in r.json()["error"]["message"]
    r = office.post(sy_url, json=slot(s["BCA301"], [t["khan"]["id"]], room="101"))
    assert r.status_code == 409 and r.json()["error"]["field"] == "room"
    assert office.post(sy_url, json=slot(s["BCA301"], [t["khan"]["id"]], room="102")).status_code == 201

    # Moving a slot re-checks clashes; removing frees the time.
    moved = office.put(
        f"{API}/timetable-slots/{first.json()['id']}", json=slot(s["BCA101"], [t["khan"]["id"]], room="101")
    )
    assert moved.status_code == 409  # Khan teaches SY at 9:00 on Monday
    assert office.delete(f"{API}/timetable-slots/{first.json()['id']}").status_code == 204
    view = office.get(f"{API}/timetables/{tt['id']}").json()
    assert [x["batch"] for x in view["slots"]] == ["B1", "B2"]
    assert office.post(url, json=slot(s["BCA101"], [t["rao"]["id"]], room="101")).status_code == 201
    # One timetable per division and term; dates stay inside the year.
    dup = office.post(
        f"{API}/timetables",
        json={
            "academic_year_id": academics["year"],
            "division_id": academics["div"][1],
            "term": 1,
            "valid_from": "2026-06-15",
            "valid_to": "2026-10-01",
        },
    )
    assert dup.status_code == 409
    out = office.patch(f"{API}/timetables/{tt['id']}", json={"valid_to": "2027-06-30"})
    assert out.status_code == 422
    assert db.audit_log.count_documents({"action": {"$regex": "^timetable\\."}}) >= 6


def test_who_may_change_a_timetable(client, sign_in, academics):  # noqa: F811
    t = academics["teachers"]
    # HOD of Computer Science manages BCA, not BCOM; faculty only read.
    tt = make_timetable(t["hod"]["client"], academics)
    assert tt["can_manage"]
    r = t["hod"]["client"].post(
        f"{API}/timetables",
        json={
            "academic_year_id": academics["year"],
            "division_id": academics["bcom_div"],
            "term": 1,
            "valid_from": "2026-06-15",
            "valid_to": "2026-11-15",
        },
    )
    assert r.status_code == 403
    assert (
        t["comhod"]["client"]
        .post(f"{API}/timetables/{tt['id']}/slots", json=slot(academics["subjects"]["BCA101"], [t["rao"]["id"]]))
        .status_code
        == 403
    )
    rao = t["rao"]["client"]
    assert rao.get(f"{API}/timetables/{tt['id']}").json()["can_manage"] is False
    assert (
        rao.post(
            f"{API}/timetables/{tt['id']}/slots", json=slot(academics["subjects"]["BCA101"], [t["rao"]["id"]])
        ).status_code
        == 403
    )
    sign_in(client, ["accounts"])
    assert client.get(f"{API}/timetables").status_code == 403  # accounts staff don't use timetables


def test_substitutions_cancellations_and_holidays(client, academics, db):  # noqa: F811
    office = academics["office"]
    s, t = academics["subjects"], academics["teachers"]
    tt = make_timetable(office, academics)
    url = f"{API}/timetables/{tt['id']}/slots"
    c_lec = office.post(url, json=slot(s["BCA101"], [t["rao"]["id"]], day=1, room="101")).json()
    m_lec = office.post(url, json=slot(s["BCA102"], [t["khan"]["id"]], day=1, start="10:00", end="11:00")).json()
    office.post(url, json=slot(s["BCA101"], [t["rao"]["id"]], day=2))

    # Monday: C cancelled, Maths taken by Rao instead of Khan.
    r = office.post(
        f"{API}/timetable-slots/{c_lec['id']}/changes",
        json={"date": MONDAY.isoformat(), "kind": "cancelled", "reason": "Teacher on exam duty"},
    )
    assert r.status_code == 201
    wrong_day = office.post(
        f"{API}/timetable-slots/{c_lec['id']}/changes",
        json={"date": "2026-07-07", "kind": "cancelled", "reason": "x" * 5},
    )
    assert wrong_day.status_code == 422
    sub = office.post(
        f"{API}/timetable-slots/{m_lec['id']}/changes",
        json={
            "date": MONDAY.isoformat(),
            "kind": "substitute",
            "faculty_ids": [t["rao"]["id"]],
            "reason": "Khan on leave",
        },
    )
    assert sub.status_code == 201

    week = office.get(f"{API}/timetable/week", params={"division_id": academics["div"][1], "day": "2026-07-08"}).json()
    assert week["week_of"] == MONDAY.isoformat()
    monday = week["days"][0]["lectures"]
    assert [x["status"] for x in monday] == ["cancelled", "substitute"]
    assert monday[1]["substitute"] == ["Anita Rao"] and monday[0]["change_reason"] == "Teacher on exam duty"

    rao = t["rao"]["client"].get(f"{API}/timetable/week", params={"mine": True, "day": MONDAY.isoformat()}).json()
    assert [x["subject_code"] for x in rao["days"][0]["lectures"]] == ["BCA101", "BCA102"]
    khan = t["khan"]["client"].get(f"{API}/timetable/week", params={"mine": True, "day": MONDAY.isoformat()}).json()
    assert [x["status"] for x in khan["days"][0]["lectures"]] == ["handed_over"]

    # The student sees the same changes; a holiday has no lectures.
    db.holidays.insert_one(
        {
            "academic_year_id": db.academic_years.find_one()["_id"],
            "date": "2026-07-07",
            "name": "Ashadhi Ekadashi",
            "status": "active",
        }
    )
    student = __import__("tests.fees_fixtures", fromlist=["new_client"]).new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    mine = student.get(f"{API}/me/timetable", params={"day": MONDAY.isoformat()}).json()
    assert [x["status"] for x in mine["days"][0]["lectures"]] == ["cancelled", "substitute"]
    assert mine["days"][1]["holiday"] == "Ashadhi Ekadashi" and mine["days"][1]["lectures"] == []
    assert student.get(f"{API}/timetables").status_code == 403

    # Undo the cancellation.
    assert office.delete(f"{API}/timetable-slots/{c_lec['id']}/changes/{MONDAY.isoformat()}").status_code == 204
    again = office.get(f"{API}/timetable/week", params={"division_id": academics["div"][1], "day": MONDAY.isoformat()})
    assert again.json()["days"][0]["lectures"][0]["status"] == "scheduled"
