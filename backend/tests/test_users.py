from fastapi.testclient import TestClient

from tests.conftest import login


def new_client(client):
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


STAFF = {"kind": "staff", "name": "Kavita Deshmukh", "email": "kavita@college.edu.in", "roles": ["accounts"]}
STUDENT = {"kind": "student", "name": "Ravi Patil", "prn": "2026bca012"}


def test_admin_creates_staff_with_a_temporary_password(client, sign_in, db):
    admin = sign_in(client, ["system_admin"])
    r = client.post("/api/v1/users", json=STAFF)
    assert r.status_code == 201, r.text
    created, temp = r.json()["user"], r.json()["temporary_password"]
    assert created["roles"] == ["accounts"] and created["mfa_required"] is True
    assert created["must_change_password"] is True
    assert len(temp) == 14 and temp.count("-") == 2

    newbie = new_client(client)
    me = login(newbie, "kavita@college.edu.in", temp).json()
    assert me["session_state"] == "mfa_setup"  # accounts staff must set up 2-step verification
    entry = db.audit_log.find_one({"action": "users.created"})
    assert entry["actor_id"] == admin["_id"] and entry["details"]["roles"] == ["accounts"]


def test_office_creates_students_but_not_staff(client, sign_in):
    sign_in(client, ["office"])
    r = client.post("/api/v1/users", json=STUDENT)
    assert r.status_code == 201 and r.json()["user"]["prn"] == "2026BCA012"
    assert r.json()["user"]["roles"] == ["student"]
    assert client.post("/api/v1/users", json=STAFF).status_code == 403


def test_students_cannot_be_given_staff_roles_at_creation(client, sign_in):
    sign_in(client, ["system_admin"])
    r = client.post("/api/v1/users", json={**STUDENT, "roles": ["system_admin"]})
    assert r.status_code == 201 and r.json()["user"]["roles"] == ["student"]


def test_validation(client, sign_in):
    sign_in(client, ["system_admin"])
    cases = [
        ({**STAFF, "email": None}, "email address"),
        ({**STAFF, "roles": []}, "at least one role"),
        ({**STAFF, "roles": ["student"]}, "Not a staff role"),
        ({**STAFF, "roles": ["superuser"]}, "Not a staff role"),
        ({**STUDENT, "prn": None}, "need a PRN"),
        ({**STUDENT, "prn": "bad prn!"}, "PRN may contain"),
    ]
    for body, message in cases:
        r = client.post("/api/v1/users", json=body)
        assert r.status_code == 422 and message in r.json()["error"]["message"], body


def test_duplicate_email_and_prn(client, sign_in):
    sign_in(client, ["system_admin"])
    client.post("/api/v1/users", json=STAFF)
    client.post("/api/v1/users", json=STUDENT)
    r = client.post("/api/v1/users", json={**STAFF, "email": "KAVITA@college.edu.in", "name": "Someone"})
    assert r.status_code == 409 and r.json()["error"]["field"] == "email"
    r = client.post("/api/v1/users", json={**STUDENT, "name": "Other"})
    assert r.status_code == 409 and r.json()["error"]["field"] == "prn"


def test_people_without_user_permissions_get_403(client, sign_in):
    sign_in(client, ["faculty"])
    assert client.get("/api/v1/users").status_code == 403
    assert client.post("/api/v1/users", json=STUDENT).status_code == 403


def test_principal_reads_but_cannot_change(client, sign_in):
    sign_in(client, ["principal"])
    assert client.get("/api/v1/users").status_code == 200
    assert client.post("/api/v1/users", json=STUDENT).status_code == 403


def test_list_and_search(client, sign_in):
    sign_in(client, ["system_admin"], name="Admin One")
    client.post("/api/v1/users", json=STAFF)
    client.post("/api/v1/users", json=STUDENT)
    assert client.get("/api/v1/users").json()["total"] == 3
    assert [u["name"] for u in client.get("/api/v1/users?search=ravi").json()["items"]] == ["Ravi Patil"]
    assert client.get("/api/v1/users?kind=student").json()["total"] == 1
    assert client.get("/api/v1/users?role=accounts").json()["total"] == 1
    assert client.get("/api/v1/users?search=.*").json()["total"] == 0  # search text is not a regex


def test_only_admins_change_roles(client, sign_in):
    admin_client, office_client = client, new_client(client)
    sign_in(admin_client, ["system_admin"])
    staff_id = admin_client.post("/api/v1/users", json=STAFF).json()["user"]["id"]
    sign_in(office_client, ["office"])
    assert office_client.patch(f"/api/v1/users/{staff_id}", json={"roles": ["system_admin"]}).status_code == 403
    r = admin_client.patch(
        f"/api/v1/users/{staff_id}", json={"roles": ["accounts", "office"], "reason": "Covers office"}
    )
    assert r.status_code == 200 and r.json()["roles"] == ["accounts", "office"]


def test_role_change_signs_the_user_out(client, sign_in):
    sign_in(client, ["system_admin"])
    body = client.post("/api/v1/users", json={**STAFF, "roles": ["office"]}).json()
    staff = new_client(client)
    login(staff, STAFF["email"], body["temporary_password"])
    client.patch(f"/api/v1/users/{body['user']['id']}", json={"roles": ["faculty"]})
    assert staff.get("/api/v1/auth/me").status_code == 401


def test_disable_and_enable(client, sign_in, db):
    sign_in(client, ["office"])
    body = client.post("/api/v1/users", json=STUDENT).json()
    student = new_client(client)
    login(student, "2026BCA012", body["temporary_password"])
    r = client.patch(f"/api/v1/users/{body['user']['id']}", json={"status": "disabled", "reason": "Left college"})
    assert r.json()["status"] == "disabled"
    assert student.get("/api/v1/auth/me").status_code == 401
    assert login(student, "2026BCA012", body["temporary_password"]).status_code == 403
    assert db.audit_log.find_one({"action": "users.updated"})["reason"] == "Left college"
    client.patch(f"/api/v1/users/{body['user']['id']}", json={"status": "active"})
    assert login(student, "2026BCA012", body["temporary_password"]).status_code == 200


def test_cannot_disable_yourself_or_remove_the_last_admin(client, sign_in):
    admin = sign_in(client, ["system_admin"])
    me = str(admin["_id"])
    r = client.patch(f"/api/v1/users/{me}", json={"status": "disabled"})
    assert r.status_code == 409
    r = client.patch(f"/api/v1/users/{me}", json={"roles": ["principal"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"


def test_reset_password(client, sign_in):
    sign_in(client, ["office"])
    body = client.post("/api/v1/users", json=STUDENT).json()
    student = new_client(client)
    login(student, "2026BCA012", body["temporary_password"])
    r = client.post(f"/api/v1/users/{body['user']['id']}/reset-password", json={"reason": "Forgot password at desk"})
    temp = r.json()["temporary_password"]
    assert student.get("/api/v1/auth/me").status_code == 401  # old sessions ended
    assert login(student, "2026BCA012", body["temporary_password"]).status_code == 401
    assert login(student, "2026BCA012", temp).json()["must_change_password"] is True


def test_office_cannot_reset_staff_passwords(client, sign_in):
    admin_client = new_client(client)
    sign_in(admin_client, ["system_admin"])
    staff_id = admin_client.post("/api/v1/users", json=STAFF).json()["user"]["id"]
    sign_in(client, ["office"])
    assert client.post(f"/api/v1/users/{staff_id}/reset-password", json={}).status_code == 403


def test_unlock(client, sign_in):
    sign_in(client, ["office"])
    body = client.post("/api/v1/users", json=STUDENT).json()
    student = new_client(client)
    for _ in range(5):
        login(student, "2026BCA012", "wrong-password-x")
    assert client.get(f"/api/v1/users/{body['user']['id']}").json()["locked"] is True
    assert client.post(f"/api/v1/users/{body['user']['id']}/unlock").json()["locked"] is False
    assert login(student, "2026BCA012", body["temporary_password"]).status_code == 200


def test_bad_ids_are_404(client, sign_in):
    sign_in(client, ["system_admin"])
    assert client.get("/api/v1/users/not-an-id").status_code == 404
    assert client.get("/api/v1/users/64b7f0000000000000000000").status_code == 404


def test_role_catalog(client, sign_in):
    sign_in(client, ["office"])
    roles = {r["id"]: r for r in client.get("/api/v1/users/roles").json()}
    assert "student" not in roles and roles["accounts"]["mfa_required"] is True
