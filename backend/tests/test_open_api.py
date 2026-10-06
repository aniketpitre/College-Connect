from tests.fees_fixtures import college, fees, new_client  # noqa: F401

API = "/api/v1"


def test_api_keys_scopes_paging_revocation_and_docs(client, sign_in, db, fees):  # noqa: F811
    principal, admin = new_client(client), new_client(client)
    sign_in(principal, ["principal"])
    sign_in(admin, ["system_admin"])
    assert admin.post(f"{API}/api-keys", json={"name": "Website", "scopes": ["notices:read"]}).status_code == 403
    assert principal.post(f"{API}/api-keys", json={"name": "Portal", "scopes": ["grades:write"]}).status_code == 422

    made = principal.post(
        f"{API}/api-keys", json={"name": "University portal sync", "scopes": ["students:read", "setup:read"]}
    ).json()
    key = made["key"]
    assert key.startswith(f"cc_{made['prefix']}_") and made["state"] == "active"
    listed = principal.get(f"{API}/api-keys").json()["keys"]
    assert "key" not in listed[0] and listed[0]["prefix"] == made["prefix"]
    assert db.api_keys.find_one({})["hash"] != key  # only a hash is stored

    other = new_client(client)  # another system: no cookies, only the key
    other.cookies.clear()
    auth = {"Authorization": f"Bearer {key}"}
    page = other.get(f"{API}/open/students", params={"limit": 2}, headers=auth).json()
    assert [s["prn"] for s in page["data"]] == ["2026BCA001", "2026BCA002"] and page["next_after"]
    rest = other.get(f"{API}/open/students", params={"limit": 2, "after": page["next_after"]}, headers=auth).json()
    assert [s["prn"] for s in rest["data"]] == ["2026BCA003"] and rest["next_after"] is None
    assert "aadhaar" not in str(page) and "phone" not in page["data"][0]
    assert other.get(f"{API}/open/setup", headers={"X-API-Key": key}).json()["programmes"][0]["code"] == "BCA"
    no_scope = other.get(f"{API}/open/fees/balances", params={"academic_year_id": fees["year"]}, headers=auth)
    assert no_scope.status_code == 403
    assert other.get(f"{API}/open/students").status_code == 401
    assert other.get(f"{API}/open/students", headers={"Authorization": "Bearer cc_deadbeef_nope"}).status_code == 401
    assert db.api_keys.find_one({})["calls"] == 3  # two student pages and setup

    # The published docs cover only the open API.
    spec = other.get(f"{API}/open/openapi.json").json()
    assert spec["servers"] == [{"url": "/api/v1"}] and all(p.startswith("/open/") for p in spec["paths"])
    assert "/open/students" in spec["paths"] and "/open/docs" not in spec["paths"]
    assert "students:read" in spec["info"]["description"]
    assert "swagger" in other.get(f"{API}/open/docs").text.lower()

    principal.post(f"{API}/api-keys/{made['id']}/revoke")
    assert other.get(f"{API}/open/students", headers=auth).status_code == 401
    assert db.audit_log.count_documents({"action": {"$in": ["api_keys.created", "api_keys.revoked"]}}) == 2
