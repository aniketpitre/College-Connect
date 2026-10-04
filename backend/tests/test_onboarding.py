from fastapi.testclient import TestClient

from tests.conftest import login
from tests.test_students import college, sign_in_as_student  # noqa: F401 - pytest fixture

API = "/api/v1/me/onboarding"


def new_client(client):
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


def _student(client, sign_in, college, **extra):  # noqa: F811
    office = new_client(client)
    sign_in(office, ["office"])
    body = {
        "prn": "2026BCA001",
        "name": "Rohan Patil",
        "programme_id": college["bca"],
        "year_of_study": 1,
        "phone": "9876543210",
        "dob": "2010-01-01",
        **extra,
    }
    return office.post("/api/v1/students", json=body).json()


def test_first_sign_in_flow(client, sign_in, college, db):  # noqa: F811
    created = _student(client, sign_in, college)
    me = login(client, "2026BCA001", created["temporary_password"]).json()
    assert me["onboarding_required"] is True and me["must_change_password"] is True
    assert client.get(API).status_code == 403  # the password comes first
    client.post(
        "/api/v1/auth/password/change",
        json={"current_password": created["temporary_password"], "new_password": "monsoon-chai-at-dawn"},
    )

    status = client.get(API).json()
    assert status["phone"] == "9876543210" and status["under_18"] is True and status["guardian_consent"] is False
    body = {
        "phone": "98220 12345",
        "email": "rohan@example.in",
        "accept_privacy": True,
        "privacy_version": status["privacy_version"],
        "language": "mr",
    }
    assert client.post(API, json={**body, "accept_privacy": False}).status_code == 422
    stale = client.post(API, json={**body, "privacy_version": "2020-01"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "notice_changed"

    done = client.post(API, json=body)
    assert done.status_code == 200 and done.json()["done"] is True
    me = client.get("/api/v1/auth/me").json()
    assert me["onboarding_required"] is False and me["language"] == "mr"
    consent = db.consents.find_one()
    assert consent["version"] == status["privacy_version"] and consent["language"] == "mr"
    student = db.students.find_one({"prn": "2026BCA001"})
    assert student["phone"] == "9822012345" and student["email"] == "rohan@example.in"
    assert db.users.find_one({"prn": "2026BCA001"})["email"] == "rohan@example.in"
    assert db.audit_log.find_one({"action": "students.contact_confirmed"})["details"]["before"]["phone"] == "9876543210"


def test_staff_have_no_onboarding(client, sign_in):
    sign_in(client, ["office"])
    assert client.get("/api/v1/auth/me").json()["onboarding_required"] is False
    assert client.get(API).status_code == 403


def test_language_preference(client, sign_in, college, db):  # noqa: F811
    _student(client, sign_in, college)
    sign_in_as_student(client, db, "2026BCA001")
    assert client.patch("/api/v1/me/preferences", json={"language": "hi"}).status_code == 204
    assert client.get("/api/v1/auth/me").json()["language"] == "hi"
    assert client.patch("/api/v1/me/preferences", json={"language": "fr"}).status_code == 422
