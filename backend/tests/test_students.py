from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from tests.conftest import login

API = "/api/v1/students"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF = b"%PDF-1.4\n" + b"x" * 100


def new_client(client):
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


@pytest.fixture
def college(db):
    """BCA (FY/SY/TY) with division A in each year, and two categories."""
    now = datetime.now(UTC)
    meta = {"status": "active", "created_at": now, "updated_at": now}
    dept = db.departments.insert_one({"code": "CS", "name": "Computer Science", **meta}).inserted_id
    bca = db.programmes.insert_one(
        {
            "code": "BCA",
            "name": "Bachelor of Computer Applications",
            "department_id": dept,
            "level": "UG",
            "duration_years": 3,
            "semesters_per_year": 2,
            "year_labels": ["FY", "SY", "TY"],
            **meta,
        }
    ).inserted_id
    divisions = {
        y: db.divisions.insert_one({"programme_id": bca, "year_of_study": y, "name": "A", **meta}).inserted_id
        for y in (1, 2, 3)
    }
    open_cat = db.categories.insert_one({"code": "OPEN", "name": "Open", **meta}).inserted_id
    obc = db.categories.insert_one({"code": "OBC", "name": "Other Backward Class", **meta}).inserted_id
    return {"bca": str(bca), "div": {y: str(d) for y, d in divisions.items()}, "open": str(open_cat), "obc": str(obc)}


def _new(college, **extra) -> dict:
    return {
        "prn": "2026bca001",
        "name": "Rohan Patil",
        "programme_id": college["bca"],
        "year_of_study": 1,
        "division_id": college["div"][1],
        "category_id": college["open"],
        "gender": "male",
        "dob": "2007-04-12",
        "phone": "+91 98765 43210",
        "aadhaar": "2345 6789 0123",
        "guardian": {"name": "Suresh Patil", "relation": "Father", "phone": "9822012345"},
        **extra,
    }


def _office(client, sign_in):
    sign_in(client, ["office"])
    return client


def _create(client, college, **extra) -> dict:
    r = client.post(API, json=_new(college, **extra))
    assert r.status_code == 201, r.text
    return r.json()


def test_office_creates_student_with_login(client, sign_in, college, db):
    _office(client, sign_in)
    body = _create(client, college)
    s = body["student"]
    assert s["prn"] == "2026BCA001" and s["programme_code"] == "BCA" and s["year_label"] == "FY"
    assert s["division"] == "A" and s["category_code"] == "OPEN"
    assert s["phone"] == "9876543210"
    assert s["aadhaar_masked"] == "XXXX XXXX 0123"
    raw = db.students.find_one({"prn": "2026BCA001"})
    assert "234567890123" not in str(raw) and raw["aadhaar_last4"] == "0123"  # full Aadhaar never stored

    student = new_client(client)
    me = login(student, "2026BCA001", body["temporary_password"]).json()
    assert me["kind"] == "student" and me["must_change_password"] is True
    assert db.audit_log.find_one({"action": "students.created"})


def test_validation_and_duplicates(client, sign_in, college):
    _office(client, sign_in)
    _create(client, college)
    dup = client.post(API, json=_new(college))
    assert dup.status_code == 409 and dup.json()["error"]["field"] == "prn"
    cases = [
        ({"year_of_study": 4}, "year_of_study"),
        ({"division_id": college["div"][2]}, "division_id"),  # division of SY for an FY student
        ({"phone": "12345"}, "phone"),
        ({"aadhaar": "1234"}, None),  # only 4 digits given: accepted as the last 4
        ({"aadhaar": "0123 4567 8901"}, "aadhaar"),
        ({"prn": "bad prn!"}, "prn"),
        ({"dob": "2090-01-01"}, "dob"),
    ]
    for i, (extra, field) in enumerate(cases):
        r = client.post(API, json=_new(college, **{"prn": f"2026BCA1{i:02d}", **extra}))
        if field is None:
            assert r.status_code == 201, r.text
        else:
            assert r.status_code == 422 and r.json()["error"]["field"] == field, (extra, r.json())


def test_list_search_and_filters(client, sign_in, college):
    _office(client, sign_in)
    _create(client, college)
    _create(client, college, prn="2026BCA002", name="Neha Joshi", year_of_study=2, division_id=college["div"][2])
    assert client.get(API).json()["total"] == 2
    assert [s["name"] for s in client.get(API, params={"q": "neha"}).json()["items"]] == ["Neha Joshi"]
    assert client.get(API, params={"q": "2026bca00"}).json()["total"] == 2
    assert client.get(API, params={"year_of_study": 2}).json()["items"][0]["year_label"] == "SY"
    assert client.get(API, params={"q": ".*"}).json()["total"] == 0


def test_update_is_audited_and_syncs_the_login(client, sign_in, college, db):
    _office(client, sign_in)
    sid = _create(client, college)["student"]["id"]
    r = client.patch(f"{API}/{sid}", json={"name": "Rohan S. Patil", "email": "rohan@example.in", "reason": "Spelling"})
    assert r.status_code == 200 and r.json()["name"] == "Rohan S. Patil"
    user = db.users.find_one({"prn": "2026BCA001"})
    assert user["name"] == "Rohan S. Patil" and user["email"] == "rohan@example.in"

    no_reason = client.patch(f"{API}/{sid}", json={"status": "tc"})
    assert no_reason.status_code == 422 and no_reason.json()["error"]["field"] == "reason"
    moved = client.patch(f"{API}/{sid}", json={"year_of_study": 2})
    assert moved.json()["division_id"] is None  # old division belonged to FY

    history = client.get(f"{API}/{sid}/history").json()
    updated = next(h for h in history if h["action"] == "students.updated" and h["reason"] == "Spelling")
    assert updated["details"]["before"]["name"] == "Rohan Patil"
    assert updated["details"]["after"]["name"] == "Rohan S. Patil"


def test_student_sees_only_their_own_record(client, sign_in, college, db):
    _office(client, sign_in)
    mine = _create(client, college)
    other = _create(client, college, prn="2026BCA002", name="Neha Joshi")
    client.post(f"{API}/{other['student']['id']}/photo", files={"file": ("n.png", PNG, "image/png")})
    other_photo = client.get(f"{API}/{other['student']['id']}").json()["photo_url"]

    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    me = student.get("/api/v1/me/student").json()
    assert me["prn"] == "2026BCA001" and me["guardian"]["name"] == "Suresh Patil"
    assert student.get(API).status_code == 403
    assert student.get(f"{API}/{other['student']['id']}").status_code == 403
    assert student.get(f"{API}/{mine['student']['id']}").status_code == 403  # even their own, via staff routes
    assert student.get(f"/api/v1{other_photo}").status_code == 404  # another student's file


def sign_in_as_student(client, db, prn):
    """Gives `client` an active session for the student with this PRN (skips the forced password change)."""
    from datetime import timedelta

    from app.core.security import new_token, token_hash

    user = db.users.find_one({"prn": prn})
    db.users.update_one({"_id": user["_id"]}, {"$set": {"must_change_password": False}})
    token = new_token()
    now = datetime.now(UTC)
    db.sessions.insert_one(
        {
            "_id": token_hash(token),
            "sid": f"s-{prn}",
            "user_id": user["_id"],
            "state": "active",
            "created_at": now,
            "last_seen_at": now,
            "expires_at": now + timedelta(hours=1),
        }
    )
    client.cookies.set("cc_session", token)


def test_change_request_flow(client, sign_in, college, db):
    _office(client, sign_in)
    sid = _create(client, college)["student"]["id"]
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")

    r = student.post(
        "/api/v1/me/student/change-requests",
        json={
            "changes": {"name": "Rohan Suresh Patil", "category_id": college["obc"]},
            "reason": "As on my HSC marksheet",
        },
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["current"]["name"] == "Rohan Patil" and req["status"] == "pending"
    again = student.post(
        "/api/v1/me/student/change-requests", json={"changes": {"name": "R. Patil"}, "reason": "Another try"}
    )
    assert again.status_code == 409  # one pending request per field
    same = student.post(
        "/api/v1/me/student/change-requests", json={"changes": {"gender": "male"}, "reason": "No change"}
    )
    assert same.status_code == 422

    queue = client.get(f"{API}/change-requests").json()
    assert len(queue) == 1 and queue[0]["prn"] == "2026BCA001"
    reject_without_reason = client.post(f"{API}/change-requests/{req['id']}/decide", json={"approve": False})
    assert reject_without_reason.status_code == 422
    ok = client.post(
        f"{API}/change-requests/{req['id']}/decide", json={"approve": True, "reason": "Checked HSC marksheet"}
    )
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    record = client.get(f"{API}/{sid}").json()
    assert record["name"] == "Rohan Suresh Patil" and record["category_code"] == "OBC"
    assert db.users.find_one({"prn": "2026BCA001"})["name"] == "Rohan Suresh Patil"
    twice = client.post(f"{API}/change-requests/{req['id']}/decide", json={"approve": True})
    assert twice.status_code == 409
    assert student.get("/api/v1/me/student/change-requests").json()[0]["status"] == "approved"
    assert [c["code"] for c in student.get("/api/v1/me/student/options").json()["categories"]] == ["OBC", "OPEN"]
    assert student.post(f"{API}/change-requests/{req['id']}/decide", json={"approve": True}).status_code == 403


def test_documents_and_photo(client, sign_in, college, db):
    _office(client, sign_in)
    sid = _create(client, college)["student"]["id"]
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")

    bad = student.post(
        "/api/v1/me/student/documents",
        data={"type": "hsc_marksheet"},
        files={"file": ("x.pdf", b"MZ not a pdf", "application/pdf")},
    )
    assert bad.status_code == 415  # type is decided from the bytes, not the name
    big = student.post(
        "/api/v1/me/student/documents",
        data={"type": "hsc_marksheet"},
        files={"file": ("x.pdf", b"%PDF-" + b"x" * (2 * 1024 * 1024), "application/pdf")},
    )
    assert big.status_code == 413
    r = student.post(
        "/api/v1/me/student/documents",
        data={"type": "hsc_marksheet"},
        files={"file": ("hsc.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 200
    doc = r.json()["documents"][0]
    assert doc["status"] == "pending"
    file_response = student.get(f"/api/v1{doc['url']}")
    assert file_response.status_code == 200 and file_response.content == PDF
    assert file_response.headers["content-security-policy"] == "sandbox"

    no_reason = client.post(f"{API}/{sid}/documents/{doc['id']}/decide", json={"verified": False})
    assert no_reason.status_code == 422
    rejected = client.post(
        f"{API}/{sid}/documents/{doc['id']}/decide", json={"verified": False, "reason": "Blurred scan"}
    )
    assert rejected.json()["documents"][0]["status"] == "rejected"
    assert student.get("/api/v1/me/student").json()["documents"][0]["reason"] == "Blurred scan"

    office_doc = client.post(
        f"{API}/{sid}/documents",
        data={"type": "leaving_certificate"},
        files={"file": ("lc.pdf", PDF, "application/pdf")},
    )
    assert office_doc.json()["documents"][1]["status"] == "verified"
    photo_pdf = student.post("/api/v1/me/student/photo", files={"file": ("p.pdf", PDF, "application/pdf")})
    assert photo_pdf.status_code == 415
    photo = student.post("/api/v1/me/student/photo", files={"file": ("p.png", PNG, "image/png")})
    assert photo.json()["has_photo"] is True


def test_permissions(client, sign_in, college):
    _office(client, sign_in)
    sid = _create(client, college)["student"]["id"]
    accounts = new_client(client)
    sign_in(accounts, ["accounts"])
    assert accounts.get(f"{API}/{sid}").status_code == 200  # accounts reads the record
    assert accounts.patch(f"{API}/{sid}", json={"name": "Other Name"}).status_code == 403
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    assert faculty.get(API).status_code == 403  # scoped access comes with class assignments (Phase 2)


def test_users_api_refuses_student_detail_edits(client, sign_in, college):
    _office(client, sign_in)
    user_id = _create(client, college)["student"]["user_id"]
    r = client.patch(f"/api/v1/users/{user_id}", json={"name": "Changed Here"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "use_students_page"
