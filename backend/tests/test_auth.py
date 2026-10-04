from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.security import hash_password
from tests.conftest import PASSWORD, login


def test_staff_login_by_email_and_student_by_prn(client, make_user):
    make_user(email="Teacher@College.test", name="Asha Kulkarni")
    r = login(client, "  teacher@college.TEST ")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Asha Kulkarni" and r.json()["session_state"] == "active"
    assert "cc_session" in r.cookies

    student_client = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
    make_user(kind="student", prn="2026bca007", name="Ravi Patil")
    r = login(student_client, "2026BCA007")
    assert r.status_code == 200 and r.json()["kind"] == "student"


def test_session_cookie_is_httponly_secure_lax(client, make_user):
    make_user()
    r = login(client, "staff@college.test")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_wrong_password_and_unknown_account_look_the_same(client, make_user):
    make_user()
    wrong = login(client, "staff@college.test", "nope-nope-nope")
    unknown = login(client, "ghost@college.test", "nope-nope-nope")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_five_wrong_passwords_lock_the_account(client, make_user, db):
    user = make_user()
    for _ in range(5):
        assert login(client, "staff@college.test", "wrong-password-x").status_code == 401
    locked = login(client, "staff@college.test")  # even the right password is refused while locked
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "account_locked"
    actions = [e["action"] for e in db.audit_log.find({"actor_id": user["_id"]})]
    assert "auth.account.locked" in actions

    db.users.update_one({"_id": user["_id"]}, {"$set": {"locked_until": datetime.now(UTC) - timedelta(seconds=1)}})
    assert login(client, "staff@college.test").status_code == 200


def test_ip_rate_limit(client, make_user):
    make_user()
    codes = [login(client, "nobody@college.test", "x").status_code for _ in range(31)]
    assert codes[-1] == 429 and set(codes[:30]) == {401}


def test_disabled_account_cannot_sign_in(client, make_user, db):
    user = make_user()
    db.users.update_one({"_id": user["_id"]}, {"$set": {"status": "disabled"}})
    r = login(client, "staff@college.test")
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"


def test_me_requires_a_session(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_signed_in"


def test_me_never_returns_secrets(client, make_user):
    make_user()
    login(client, "staff@college.test")
    me = client.get("/api/v1/auth/me").json()
    assert "password_hash" not in me and "mfa" not in me
    assert me["permissions"] == []  # faculty has no permissions yet in Phase 1A


def test_logout_ends_the_session(client, make_user, db):
    make_user()
    login(client, "staff@college.test")
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert db.sessions.count_documents({}) == 0


def test_only_token_hashes_are_stored(client, make_user, db):
    make_user()
    token = login(client, "staff@college.test").cookies["cc_session"]
    stored = db.sessions.find_one()
    assert stored["_id"] != token and len(stored["_id"]) == 64


def test_expired_sessions_are_rejected(client, make_user, db):
    make_user()
    login(client, "staff@college.test")
    db.sessions.update_many({}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_lifetimes(client, make_user, db):
    make_user()
    make_user(kind="student")
    login(client, "staff@college.test")
    staff = db.sessions.find_one()
    assert timedelta(hours=11) < staff["expires_at"] - staff["created_at"] <= timedelta(hours=12)
    db.sessions.delete_many({})
    login(client, "2026BCA001")
    student = db.sessions.find_one()
    assert student["expires_at"] - student["created_at"] > timedelta(days=29)


def test_cookie_requests_without_the_csrf_header_are_blocked(client, make_user):
    make_user()
    token = login(client, "staff@college.test").cookies["cc_session"]
    bare = TestClient(client.app, base_url="https://testserver", cookies={"cc_session": token})
    r = bare.post("/api/v1/auth/logout")
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    assert bare.get("/api/v1/auth/me").status_code == 200  # reads are fine


def test_forced_password_change_flow(client, make_user, db):
    make_user(kind="student", must_change_password=True, password="k7mr-x4tq-9bhn")
    me = login(client, "2026BCA001", "k7mr-x4tq-9bhn").json()
    assert me["must_change_password"] is True
    assert client.get("/api/v1/auth/sessions").json()["error"]["code"] == "password_change_required"

    weak = client.post(
        "/api/v1/auth/password/change", json={"current_password": "k7mr-x4tq-9bhn", "new_password": "password123"}
    )
    assert weak.status_code == 422 and weak.json()["error"]["field"] == "new_password"

    r = client.post(
        "/api/v1/auth/password/change", json={"current_password": "k7mr-x4tq-9bhn", "new_password": "my own secret 42"}
    )
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert client.get("/api/v1/auth/sessions").status_code == 200
    assert login(client, "2026BCA001", "my own secret 42").status_code == 200


def test_password_change_signs_out_other_devices(client, make_user, db):
    make_user()
    other = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
    login(other, "staff@college.test")
    login(client, "staff@college.test")
    r = client.post(
        "/api/v1/auth/password/change", json={"current_password": PASSWORD, "new_password": "brand new pass 99"}
    )
    assert r.status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 200
    assert db.sessions.count_documents({}) == 1


def test_password_policy(client, make_user):
    make_user(name="Meera Joshi", email="meera@college.test")
    login(client, "meera@college.test")
    for bad, msg in [("short", "at least"), ("collegeconnect", "too common"), ("meera-secret-2026", "name")]:
        r = client.post("/api/v1/auth/password/change", json={"current_password": PASSWORD, "new_password": bad})
        assert r.status_code == 422 and msg in r.json()["error"]["message"], bad


def test_old_hashes_are_upgraded_on_login(client, make_user, db):
    from argon2 import PasswordHasher

    user = make_user()
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8192).hash(PASSWORD)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": weak_hash}})
    login(client, "staff@college.test")
    assert db.users.find_one({"_id": user["_id"]})["password_hash"] != weak_hash


def test_devices_list_and_end_one(client, make_user):
    make_user()
    phone = TestClient(
        client.app, base_url="https://testserver", headers={"X-Requested-With": "x", "User-Agent": "Phone"}
    )
    login(phone, "staff@college.test")
    login(client, "staff@college.test")
    sessions = client.get("/api/v1/auth/sessions").json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/v1/auth/sessions/{other['id']}").status_code == 204
    assert phone.get("/api/v1/auth/me").status_code == 401


def test_logout_everywhere(client, make_user):
    make_user()
    phone = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
    login(phone, "staff@college.test")
    login(client, "staff@college.test")
    assert client.post("/api/v1/auth/logout-all").json() == {"signed_out_sessions": 2}
    assert phone.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_history_is_recorded(client, make_user):
    make_user()
    login(client, "staff@college.test", "wrong-password-x")
    login(client, "staff@college.test")
    history = client.get("/api/v1/auth/login-history").json()
    assert [h["action"] for h in history[:2]] == ["auth.login.succeeded", "auth.login.failed"]
    assert history[1]["reason"] == "wrong_password"


def test_first_admin_setup(client, db, monkeypatch):
    assert client.get("/api/v1/auth/setup").json() == {"needs_setup": False}  # no SETUP_TOKEN configured
    monkeypatch.setenv("SETUP_TOKEN", "one-time-setup-token")
    assert client.get("/api/v1/auth/setup").json() == {"needs_setup": True}

    body = {
        "setup_token": "wrong",
        "name": "Principal Office",
        "email": "admin@college.edu.in",
        "password": "Shivaji Park 1974!",
    }
    assert client.post("/api/v1/auth/setup", json=body).status_code == 403

    body["setup_token"] = "one-time-setup-token"
    r = client.post("/api/v1/auth/setup", json=body)
    assert r.status_code == 201 and r.json()["roles"] == ["system_admin"]
    assert client.get("/api/v1/auth/setup").json() == {"needs_setup": False}
    assert client.post("/api/v1/auth/setup", json=body).status_code == 409

    me = login(client, "admin@college.edu.in", "Shivaji Park 1974!").json()
    assert me["session_state"] == "mfa_setup"  # admins must set up 2-step verification first
    assert client.get("/api/v1/auth/sessions").json()["error"]["code"] == "mfa_setup_required"


def test_hash_password_is_argon2id():
    assert hash_password("x" * 12).startswith("$argon2id$")
