import re

from fastapi.testclient import TestClient

from app.core import email
from tests.conftest import login

NEW = "monsoon-chai-at-dawn"


def _link_token() -> str:
    match = re.search(r"/reset-password#(\S+)", email.OUTBOX[-1].text)
    assert match
    return match.group(1)


def test_reset_by_email_link(client, make_user, db):
    email.OUTBOX.clear()
    make_user(email="teacher@college.test")
    other_device = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
    login(other_device, "teacher@college.test")

    r = client.post("/api/v1/auth/password/forgot", json={"identifier": "Teacher@college.test"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert email.OUTBOX[-1].to == "teacher@college.test"
    token = _link_token()
    assert db.password_resets.find_one()["_id"] != token  # only the hash is stored

    weak = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "password123"})
    assert weak.status_code == 422
    ok = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": NEW})
    assert ok.status_code == 200
    assert other_device.get("/api/v1/auth/me").status_code == 401  # signed out everywhere
    assert login(client, "teacher@college.test", NEW).status_code == 200
    again = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": NEW + "x"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_token"


def test_unknown_account_gets_the_same_answer_and_no_email(client, make_user):
    email.OUTBOX.clear()
    make_user(kind="student", prn="2026BCA009")  # students without email can't self-reset
    a = client.post("/api/v1/auth/password/forgot", json={"identifier": "ghost@college.test"})
    b = client.post("/api/v1/auth/password/forgot", json={"identifier": "2026BCA009"})
    assert a.json() == b.json() == {"ok": True}
    assert email.OUTBOX == []


def test_only_the_newest_link_works(client, make_user):
    email.OUTBOX.clear()
    make_user(email="teacher@college.test")
    client.post("/api/v1/auth/password/forgot", json={"identifier": "teacher@college.test"})
    first = _link_token()
    client.post("/api/v1/auth/password/forgot", json={"identifier": "teacher@college.test"})
    second = _link_token()
    assert client.post("/api/v1/auth/password/reset", json={"token": first, "new_password": NEW}).status_code == 400
    assert client.post("/api/v1/auth/password/reset", json={"token": second, "new_password": NEW}).status_code == 200


def test_expired_link_is_refused(client, make_user, db):
    from datetime import UTC, datetime, timedelta

    email.OUTBOX.clear()
    make_user(email="teacher@college.test")
    client.post("/api/v1/auth/password/forgot", json={"identifier": "teacher@college.test"})
    db.password_resets.update_many({}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    r = client.post("/api/v1/auth/password/reset", json={"token": _link_token(), "new_password": NEW})
    assert r.status_code == 400


def test_reset_clears_a_lockout(client, make_user, db):
    email.OUTBOX.clear()
    user = make_user(email="teacher@college.test")
    for _ in range(5):
        login(client, "teacher@college.test", "wrong-password-x")
    client.post("/api/v1/auth/password/forgot", json={"identifier": "teacher@college.test"})
    client.post("/api/v1/auth/password/reset", json={"token": _link_token(), "new_password": NEW})
    assert db.users.find_one({"_id": user["_id"]})["locked_until"] is None
    assert login(client, "teacher@college.test", NEW).status_code == 200


def test_requests_are_rate_limited_per_account(client, make_user):
    email.OUTBOX.clear()
    make_user(email="teacher@college.test")
    codes = [
        client.post("/api/v1/auth/password/forgot", json={"identifier": "teacher@college.test"}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
