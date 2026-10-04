from datetime import UTC, datetime, timedelta

import pyotp
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, login


def _new_client(client) -> TestClient:
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


def _code(secret: str, offset_seconds: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=offset_seconds))


def _turn_on(client, email: str) -> tuple[str, list[str]]:
    """Sign in (state mfa_setup for required roles) and complete set-up; returns secret and recovery codes."""
    assert login(client, email).status_code == 200
    setup = client.post("/api/v1/auth/mfa/setup").json()
    assert setup["qr_svg"].startswith("data:image/svg+xml")
    assert setup["otpauth_uri"].startswith("otpauth://totp/CollegeConnect")
    r = client.post("/api/v1/auth/mfa/enable", json={"code": _code(setup["secret"], -30)})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()["recovery_codes"]


def test_required_role_must_set_up_2_step_before_anything_else(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    r = login(client, "admin@college.test")
    assert r.json()["session_state"] == "mfa_setup"
    blocked = client.get("/api/v1/users")
    assert blocked.status_code == 401 and blocked.json()["error"]["code"] == "mfa_setup_required"

    setup = client.post("/api/v1/auth/mfa/setup").json()
    wrong = client.post("/api/v1/auth/mfa/enable", json={"code": "000000"})
    assert wrong.status_code == 400 and wrong.json()["error"]["field"] == "code"
    done = client.post("/api/v1/auth/mfa/enable", json={"code": _code(setup["secret"])})
    assert done.status_code == 200
    assert len(done.json()["recovery_codes"]) == 8
    assert done.json()["me"]["session_state"] == "active" and done.json()["me"]["mfa_enabled"]
    assert client.get("/api/v1/users").status_code == 200


def test_secret_is_stored_encrypted_and_recovery_codes_hashed(client, make_user, db):
    user = make_user(email="admin@college.test", roles=["system_admin"])
    secret, codes = _turn_on(client, "admin@college.test")
    mfa = db.users.find_one({"_id": user["_id"]})["mfa"]
    assert secret not in str(mfa) and not any(c in str(mfa) for c in codes)
    assert "pending_secret" not in mfa


def test_next_sign_in_asks_for_the_code_and_rejects_replay(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    secret, _ = _turn_on(client, "admin@college.test")

    second = _new_client(client)
    assert login(second, "admin@college.test").json()["session_state"] == "mfa_pending"
    assert second.get("/api/v1/users").json()["error"]["code"] == "mfa_required"
    # The code used to enable 2-step (previous time step) can't be used again.
    replay = second.post("/api/v1/auth/mfa/verify", json={"code": _code(secret, -30)})
    assert replay.status_code == 400
    ok = second.post("/api/v1/auth/mfa/verify", json={"code": _code(secret)})
    assert ok.status_code == 200 and ok.json()["session_state"] == "active"
    assert second.get("/api/v1/users").status_code == 200

    third = _new_client(client)
    login(third, "admin@college.test")
    assert third.post("/api/v1/auth/mfa/verify", json={"code": _code(secret)}).status_code == 400  # same code again


def test_verify_rotates_the_session_token(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    secret, _ = _turn_on(client, "admin@college.test")
    second = _new_client(client)
    login(second, "admin@college.test")
    partial_token = second.cookies.get("cc_session")
    second.post("/api/v1/auth/mfa/verify", json={"code": _code(secret, 30)})
    assert second.cookies.get("cc_session") != partial_token
    stale = _new_client(client)
    stale.cookies.set("cc_session", partial_token)
    assert stale.get("/api/v1/auth/me").status_code == 401


def test_recovery_code_works_once(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    _, codes = _turn_on(client, "admin@college.test")
    second = _new_client(client)
    login(second, "admin@college.test")
    r = second.post("/api/v1/auth/mfa/verify", json={"code": codes[0].upper().replace("-", " ")})
    assert r.status_code == 200 and r.json()["recovery_codes_left"] == 7
    third = _new_client(client)
    login(third, "admin@college.test")
    assert third.post("/api/v1/auth/mfa/verify", json={"code": codes[0]}).status_code == 400


def test_wrong_codes_are_rate_limited(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    _turn_on(client, "admin@college.test")
    second = _new_client(client)
    login(second, "admin@college.test")
    statuses = [second.post("/api/v1/auth/mfa/verify", json={"code": "123456"}).status_code for _ in range(11)]
    assert statuses[-1] == 429


def test_optional_2_step_can_be_turned_off_but_required_cannot(client, make_user, sign_in):
    make_user(email="admin@college.test", roles=["system_admin"])
    _turn_on(client, "admin@college.test")
    refused = client.post("/api/v1/auth/mfa/disable", json={"password": PASSWORD})
    assert refused.status_code == 403

    teacher = _new_client(client)
    sign_in(teacher, ["faculty"])
    setup = teacher.post("/api/v1/auth/mfa/setup").json()
    assert teacher.post("/api/v1/auth/mfa/enable", json={"code": _code(setup["secret"])}).status_code == 200
    assert teacher.get("/api/v1/auth/mfa").json()["enabled"] is True
    assert teacher.post("/api/v1/auth/mfa/disable", json={"password": "wrong"}).status_code == 400
    off = teacher.post("/api/v1/auth/mfa/disable", json={"password": PASSWORD})
    assert off.status_code == 200 and off.json()["mfa_enabled"] is False


def test_new_recovery_codes_replace_old_ones(client, make_user):
    make_user(email="admin@college.test", roles=["system_admin"])
    _, old = _turn_on(client, "admin@college.test")
    new = client.post("/api/v1/auth/mfa/recovery-codes", json={"password": PASSWORD}).json()["recovery_codes"]
    assert set(new).isdisjoint(old)
    second = _new_client(client)
    login(second, "admin@college.test")
    assert second.post("/api/v1/auth/mfa/verify", json={"code": old[0]}).status_code == 400
    assert second.post("/api/v1/auth/mfa/verify", json={"code": new[0]}).status_code == 200


def test_admin_can_reset_someones_2_step(client, make_user, sign_in, db):
    target = make_user(email="accounts@college.test", roles=["accounts"])
    accounts = _new_client(client)
    _turn_on(accounts, "accounts@college.test")

    sign_in(client, ["system_admin"])
    no_reason = client.post(f"/api/v1/users/{target['_id']}/reset-2-step", json={})
    assert no_reason.status_code == 422
    r = client.post(f"/api/v1/users/{target['_id']}/reset-2-step", json={"reason": "Lost phone, verified in person"})
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False
    assert accounts.get("/api/v1/auth/me").status_code == 401  # signed out everywhere
    assert login(accounts, "accounts@college.test").json()["session_state"] == "mfa_setup"
    assert db.audit_log.find_one({"action": "users.mfa_reset_by_staff", "target_id": target["_id"]})

    office = _new_client(client)
    sign_in(office, ["office"])
    denied = office.post(f"/api/v1/users/{target['_id']}/reset-2-step", json={"reason": "please reset"})
    assert denied.status_code == 403
