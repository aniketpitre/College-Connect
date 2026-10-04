from fastapi.testclient import TestClient

API = "/api/v1/setup"


def _admin(client, sign_in):
    sign_in(client, ["system_admin"])
    return client


def _bca(client) -> dict:
    dept = client.post(f"{API}/departments", json={"code": "cs", "name": "Computer Science"}).json()
    r = client.post(
        f"{API}/programmes",
        json={
            "code": "bca",
            "name": "Bachelor of Computer Applications",
            "department_id": dept["id"],
            "duration_years": 3,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_admin_builds_the_college_structure(client, sign_in, db):
    _admin(client, sign_in)
    bca = _bca(client)
    assert bca["code"] == "BCA" and bca["year_labels"] == ["FY", "SY", "TY"]

    div = client.post(f"{API}/divisions", json={"programme_id": bca["id"], "year_of_study": 1, "name": "a"})
    assert div.status_code == 201 and div.json()["name"] == "A"
    too_far = client.post(f"{API}/divisions", json={"programme_id": bca["id"], "year_of_study": 4, "name": "A"})
    assert too_far.status_code == 422 and too_far.json()["error"]["field"] == "year_of_study"
    dup = client.post(f"{API}/divisions", json={"programme_id": bca["id"], "year_of_study": 1, "name": "A"})
    assert dup.status_code == 409

    subject = {
        "programme_id": bca["id"],
        "semester": 1,
        "code": "bca101",
        "name": "Programming in C",
        "credits": 4,
        "max_internal": 30,
        "max_external": 70,
    }
    assert client.post(f"{API}/subjects", json=subject).status_code == 201
    assert client.post(f"{API}/subjects", json={**subject, "code": "X", "semester": 7}).status_code == 422
    listed = client.get(f"{API}/subjects", params={"programme_id": bca["id"], "semester": 1}).json()
    assert [s["code"] for s in listed] == ["BCA101"]

    assert client.post(f"{API}/categories", json={"code": "obc", "name": "Other Backward Class"}).status_code == 201
    overview = client.get(API).json()
    assert [p["code"] for p in overview["programmes"]] == ["BCA"]
    assert overview["categories"][0]["code"] == "OBC"
    assert db.audit_log.count_documents({"action": {"$regex": "^setup\\."}}) == 5


def test_academic_year_rules_and_current_switch(client, sign_in):
    _admin(client, sign_in)
    bad = client.post(
        f"{API}/academic-years", json={"name": "2026-28", "start_date": "2026-06-01", "end_date": "2027-05-31"}
    )
    assert bad.status_code == 422 and bad.json()["error"]["field"] == "name"
    backwards = client.post(
        f"{API}/academic-years", json={"name": "2026-27", "start_date": "2026-06-01", "end_date": "2026-01-01"}
    )
    assert backwards.json()["error"]["field"] == "end_date"

    y1 = client.post(
        f"{API}/academic-years", json={"name": "2026-27", "start_date": "2026-06-01", "end_date": "2027-05-31"}
    ).json()
    y2 = client.post(
        f"{API}/academic-years", json={"name": "2027-28", "start_date": "2027-06-01", "end_date": "2028-05-31"}
    ).json()
    client.post(f"{API}/academic-years/{y1['id']}/make-current")
    client.post(f"{API}/academic-years/{y2['id']}/make-current")
    years = {y["name"]: y["is_current"] for y in client.get(API).json()["academic_years"]}
    assert years == {"2026-27": False, "2027-28": True}
    assert client.get(API).json()["current_year"]["name"] == "2027-28"

    archive_current = client.patch(f"{API}/academic-years/{y2['id']}", json={"status": "archived"})
    assert archive_current.status_code == 409

    holiday = client.post(
        f"{API}/holidays", json={"academic_year_id": y1["id"], "date": "2026-08-15", "name": "Independence Day"}
    )
    assert holiday.status_code == 201
    outside = client.post(f"{API}/holidays", json={"academic_year_id": y1["id"], "date": "2027-08-15", "name": "Later"})
    assert outside.status_code == 422 and outside.json()["error"]["field"] == "date"


def test_archived_records_cannot_be_used(client, sign_in):
    _admin(client, sign_in)
    bca = _bca(client)
    dept_id = bca["department_id"]
    client.patch(f"{API}/departments/{dept_id}", json={"status": "archived"})
    r = client.post(f"{API}/programmes", json={"code": "BSC", "name": "BSc Computer Science", "department_id": dept_id})
    assert r.status_code == 422 and "archived" in r.json()["error"]["message"]


def test_update_keeps_history(client, sign_in, db):
    _admin(client, sign_in)
    bca = _bca(client)
    r = client.patch(f"{API}/programmes/{bca['id']}", json={"name": "BCA (Science)", "year_labels": ["fy", "sy", "ty"]})
    assert r.status_code == 200 and r.json()["name"] == "BCA (Science)"
    assert client.patch(f"{API}/programmes/{bca['id']}", json={"year_labels": ["FY"]}).status_code == 422
    entry = db.audit_log.find_one({"action": "setup.programmes.updated"})
    assert entry["details"]["before"]["name"] == "Bachelor of Computer Applications"
    assert entry["details"]["after"]["name"] == "BCA (Science)"


def test_institution_settings(client, sign_in):
    _admin(client, sign_in)
    assert client.get(API).json()["institution"]["receipt_prefix"] == "R"
    r = client.put(f"{API}/institution", json={"name": "Shivaji College of Computer Science", "university": "SPPU"})
    assert r.status_code == 200 and r.json()["university"] == "SPPU"
    assert client.put(f"{API}/institution", json={"name": "X"}).status_code == 422


def test_starter_data_is_idempotent(client, sign_in, db):
    _admin(client, sign_in)
    first = client.post(f"{API}/starter-data").json()
    assert first["categories"] == 8 and first["programmes"] == 1 and first["divisions"] == 3
    assert first["academic_years"] == 1
    second = client.post(f"{API}/starter-data").json()
    assert sum(second.values()) == 0
    assert client.get(API).json()["current_year"] is not None


def test_staff_can_read_but_only_admin_can_change(client, sign_in):
    _admin(client, sign_in)
    _bca(client)
    for role in ("office", "faculty", "accounts"):
        other = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
        sign_in(other, [role])
        assert other.get(API).status_code == 200
        assert other.post(f"{API}/categories", json={"code": "X", "name": "Xyz"}).status_code == 403
    student = TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})
    sign_in(student, ["student"], kind="student", prn="2026BCA050")
    assert student.get(API).status_code == 403
