from datetime import UTC, date, datetime

from bson import ObjectId

from app.core import email
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

API = "/api/v1"
DAY = date(2026, 10, 5)
PDF = b"%PDF-1.4\n% resume\n"


def _results(db, student_id, points):
    """A published result with one 4-credit subject per grade point (0 = failed)."""
    session = db.exam_sessions.insert_one({"name": "Oct 2026", "results_published": True}).inserted_id
    subjects = [
        {
            "subject_id": ObjectId(),
            "code": f"S{i}",
            "name": f"Subject {i}",
            "semester": 1,
            "credits": 4,
            "grade_point": p,
            "grade": "A" if p else "F",
            "passed": p > 0,
        }
        for i, p in enumerate(points)
    ]
    db.results.insert_one(
        {
            "student_id": ObjectId(student_id),
            "session_id": session,
            "exam_order": 1,
            "subjects": subjects,
            "created_at": datetime.now(UTC),
        }
    )


def test_drive_eligibility_registration_rounds_offer_stats(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    at(monkeypatch, ist(DAY, 11))
    st = fees["students"]
    _results(db, st["2026BCA001"], [9, 8])  # CGPA 8.5, no backlogs
    _results(db, st["2026BCA002"], [7, 0])  # CGPA 3.5, one backlog
    officer = new_client(client)
    sign_in(officer, ["placement"])
    body = {
        "company": "Infosys", "role": "Systems Engineer", "ctc_lpa": 3.6, "register_by": "2026-10-20",
        "rounds": ["Aptitude", "Interview"],
        "eligibility": {"programme_ids": [fees["bca"]], "years": [1], "min_cgpa": 6.0, "max_backlogs": 0},
    }  # fmt: skip
    drive = officer.post(f"{API}/placement/drives", json=body).json()
    assert drive["eligibility"]["programmes"] == ["BCA"]

    rohan, neha = new_client(client), new_client(client)
    sign_in_as_student(rohan, db, "2026BCA001")
    sign_in_as_student(neha, db, "2026BCA002")
    mine = rohan.get(f"{API}/me/placement").json()
    assert mine["cgpa"] == 8.5 and mine["drives"][0]["eligible"]
    nd = neha.get(f"{API}/me/placement").json()["drives"][0]
    assert not nd["eligible"] and set(nd["reasons"]) == {"cgpa", "backlogs"}
    assert neha.post(f"{API}/me/placement/drives/{drive['id']}/register").json()["error"]["code"] == "not_eligible"
    assert rohan.post(f"{API}/me/placement/drives/{drive['id']}/register").json()["error"]["code"] == "no_resume"
    assert (
        rohan.post(
            f"{API}/me/placement/resume", files={"file": ("cv.png", b"\x89PNG\r\n\x1a\nxx", "image/png")}
        ).status_code
        == 415
    )
    rohan.post(f"{API}/me/placement/resume", files={"file": ("rohan-cv.pdf", PDF, "application/pdf")})
    reg = rohan.post(f"{API}/me/placement/drives/{drive['id']}/register").json()["drives"][0]["registration"]
    assert reg["stage"] == "Registered"

    rows = officer.get(f"{API}/placement/drives/{drive['id']}/registrations").json()["registrations"]
    assert [(r["prn"], r["cgpa"], r["backlogs"]) for r in rows] == [("2026BCA001", 8.5, 0)]
    csv = officer.get(f"{API}/placement/drives/{drive['id']}/registrations.csv").text
    assert "2026BCA001,Rohan Patil" in csv
    assert officer.get(f"{API}/placement/registrations/{rows[0]['id']}/resume").content == PDF
    assert rohan.get(f"{API}/placement/registrations/{rows[0]['id']}/resume").status_code == 403

    url = f"{API}/placement/drives/{drive['id']}/results"
    assert (
        officer.post(url, json={"registration_ids": [rows[0]["id"]], "action": "next"}).json()["registrations"][0][
            "stage"
        ]
        == "Aptitude"
    )
    officer.post(url, json={"registration_ids": [rows[0]["id"]], "action": "next"})
    assert (
        officer.post(url, json={"registration_ids": [rows[0]["id"]], "action": "next"}).json()["error"]["code"]
        == "last_round"
    )
    assert rohan.post(f"{API}/me/placement/drives/{drive['id']}/withdraw").status_code == 409  # already in the rounds
    db.students.update_one({"_id": ObjectId(st["2026BCA001"])}, {"$set": {"email": "rohan@example.com"}})
    email.OUTBOX.clear()
    officer.post(url, json={"registration_ids": [rows[0]["id"]], "action": "select", "ctc_lpa": 4.0})
    assert "selected by Infosys" in email.OUTBOX[-1].text
    assert rohan.get(f"{API}/me/placement").json()["drives"][0]["registration"]["offer_lpa"] == 4.0
    stats = officer.get(f"{API}/placement/stats").json()
    assert (stats["offers"], stats["students_placed"], stats["highest_lpa"], stats["by_programme"]) == (
        1,
        1,
        4.0,
        {"BCA": 1},
    )
    assert rohan.get(f"{API}/placement/stats").status_code == 403
