from datetime import UTC, datetime

from bson import ObjectId

from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _metrics(c, **params):
    data = c.get(f"{API}/reports/naac", params=params).json()
    return data, {m["id"]: m for m in data["metrics"]}


def test_naac_tables_gaps_and_evidence(client, sign_in, db, fees):  # noqa: F811
    db.students.update_many({}, {"$set": {"admission_date": "2026-07-01"}})
    iqac, office, faculty = new_client(client), new_client(client), new_client(client)
    sign_in(iqac, ["iqac"])
    sign_in(office, ["office"])
    teacher = sign_in(faculty, ["faculty"], name="Amit Deshmukh")

    data, m = _metrics(iqac)
    assert data["year"]["name"] == "2026-27" and len(data["metrics"]) == 14
    assert any("No sanctioned intake for BCA" in g for g in m["2.1.1"]["gaps"])
    assert any("no staff record" in g for g in m["2.4.2"]["gaps"])
    assert m["5.2.2"]["manual"] is True

    # The IQAC sets the intake and sanctioned posts; the office records the teacher.
    iqac.put(f"{API}/reports/naac/settings", json={"sanctioned_posts": 4, "intake": {fees["bca"]: 60}})
    office.put(
        f"{API}/staff/{teacher['_id']}",
        json={
            "designation": "Assistant Professor",
            "qualifications": [{"level": "pg", "degree": "M.Sc."}, {"level": "net", "degree": "UGC NET"}],
        },
    )
    _, m = _metrics(iqac)
    assert m["2.1.1"]["value"] == "5.0%" and m["2.1.1"]["rows"][0] == {
        "programme": "BCA",
        "intake": 60,
        "admitted": 3,
        "percent": 5.0,
    }
    assert m["2.4.1"]["value"] == "25.0%"
    assert any("no appointment order" in g for g in m["2.4.1"]["gaps"])
    assert m["2.4.2"]["value"] == "100.0%" and m["2.2.2"]["value"] == "3:1"
    csv = iqac.get(f"{API}/reports/naac/2.1.1.csv").text
    assert csv.splitlines() == ["Programme,Sanctioned intake,Admitted,%", "BCA,60,3,5.0"]

    # Evidence: uploaded, listed with the metric, downloaded, removed.
    assert any("No evidence uploaded" in g for g in m["2.4.2"]["gaps"])
    up = iqac.post(
        f"{API}/reports/naac/2.4.2/evidence",
        files={"file": ("net.pdf", PDF, "application/pdf")},
        data={"title": "NET certificates"},
    )
    assert up.status_code == 201
    _, m = _metrics(iqac)
    assert [e["title"] for e in m["2.4.2"]["evidence"]] == ["NET certificates"]
    assert not any("No evidence uploaded" in g for g in m["2.4.2"]["gaps"])
    assert iqac.get(f"{API}/reports/naac/evidence/{up.json()['id']}").content == PDF
    assert office.post(f"{API}/reports/naac/2.4.2/evidence", files={"file": ("x.pdf", PDF)}).status_code == 403
    assert iqac.delete(f"{API}/reports/naac/evidence/{up.json()['id']}").status_code == 204
    assert db.files.count_documents({"purpose": "naac"}) == 0

    # Who can read: office yes; teachers and students no.
    assert office.get(f"{API}/reports/naac").status_code == 200
    assert faculty.get(f"{API}/reports/naac").status_code == 403
    rohan = new_client(client)
    sign_in_as_student(rohan, db, "2026BCA001")
    assert rohan.get(f"{API}/reports/aishe").status_code == 403


def test_aishe_nirf_apaar_and_abc_credits(client, sign_in, db, fees):  # noqa: F811
    office = new_client(client)
    sign_in(office, ["office"])
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"gender": "male"}})
    db.students.update_one({"prn": "2026BCA002"}, {"$set": {"gender": "female"}})

    aishe = office.get(f"{API}/reports/aishe").json()
    row = aishe["students"][0]
    assert (row["programme"], row["year"], row["total"], row["female"], row["male"]) == ("BCA", 1, 3, 1, 1)
    assert (row["general"], row["obc"]) == (2, 1)
    assert "1 student(s) have no gender recorded." in aishe["gaps"]
    assert office.get(f"{API}/reports/aishe/students.csv").text.startswith("Programme,Year,Total,Female")
    points = {p["item"]: p["value"] for p in office.get(f"{API}/reports/nirf").json()["points"]}
    assert points["Total students"] == 3 and points["Female students"] == 1

    # APAAR: import, invalid and unknown rows reported, duplicates found.
    check = office.get(f"{API}/reports/apaar").json()
    assert len(check["missing"]) == 3 and check["valid"] == 0
    csv_file = "PRN,APAAR ID\n2026bca001,1234 5678 9012\n2026BCA002,111111111111\n2026BCA009,987654321098\n"
    out = office.post(f"{API}/reports/apaar/import", files={"file": ("apaar.csv", csv_file.encode())}).json()
    assert out["updated"] == 1 and [p["prn"] for p in out["problems"]] == ["2026BCA002", "2026BCA009"]
    assert db.students.find_one({"prn": "2026BCA001"})["apaar_id"] == "123456789012"
    db.students.update_one({"prn": "2026BCA003"}, {"$set": {"apaar_id": "123456789012"}})
    check = office.get(f"{API}/reports/apaar").json()
    assert {s["prn"] for s in check["duplicate"]} == {"2026BCA001", "2026BCA003"}

    # ABC credits: passed courses of published results, students without an APAAR ID left out.
    db.students.update_one({"prn": "2026BCA003"}, {"$unset": {"apaar_id": ""}})
    session = db.exam_sessions.insert_one(
        {"name": "Oct 2026 university exams", "academic_year_id": ObjectId(fees["year"]), "results_published": True,
         "classes": [], "created_at": datetime.now(UTC)}
    ).inserted_id  # fmt: skip
    subjects = [
        {
            "code": "BCA101",
            "name": "Programming in C",
            "semester": 1,
            "credits": 4.0,
            "grade": "A",
            "grade_point": 8,
            "passed": True,
        },
        {
            "code": "BCA102",
            "name": "Mathematics I",
            "semester": 1,
            "credits": 4.0,
            "grade": "F",
            "grade_point": 0,
            "passed": False,
        },
    ]
    for prn in ("2026BCA001", "2026BCA003"):
        sid = db.students.find_one({"prn": prn})["_id"]
        db.results.insert_one({"session_id": session, "student_id": sid, "subjects": subjects, "outcome": "fail"})
    preview = office.get(f"{API}/reports/apaar/credits").json()
    assert (preview["rows"], preview["credits"], preview["skipped_without_apaar"]) == (1, 4.0, 1)
    lines = office.get(f"{API}/reports/apaar/credits.csv").text.splitlines()
    assert lines[0].startswith("APAAR ID,PRN,Name") and lines[1].startswith(
        "123456789012,2026BCA001,Rohan Patil,BCA,1,BCA101"
    )
    assert db.audit_log.find_one({"action": "reports.abc_credits_exported"})["details"]["rows"] == 1
