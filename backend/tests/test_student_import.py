import csv
import io
from datetime import UTC, datetime

from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import login
from tests.test_students import college  # noqa: F401 - pytest fixture

API = "/api/v1/students"
HEADER = ["prn", "name", "programme", "year", "division", "gender", "dob", "category", "phone", "email"]


def new_client(client):
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


def _csv(rows: list[list[str]], header=HEADER) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode()


def _upload(client, data: bytes, name="students.csv"):
    return client.post(f"{API}/imports", files={"file": (name, data, "text/csv")})


def _row(i: int, **over) -> list[str]:
    base = {
        "prn": f"2026BCA{i:03d}",
        "name": f"Student Number{i}",
        "programme": "BCA",
        "year": "FY",
        "division": "A",
        "gender": "F",
        "dob": "12-04-2007",
        "category": "OPEN",
        "phone": f"98765{i:05d}",
        "email": "",
    }
    base.update(over)
    return [base[h] for h in HEADER]


def test_template_and_permissions(client, sign_in):
    sign_in(client, ["office"])
    r = client.get(f"{API}/imports/template.csv")
    assert r.status_code == 200 and r.text.startswith("prn,name,programme,year")
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    assert faculty.get(f"{API}/imports/template.csv").status_code == 403
    assert _upload(faculty, _csv([_row(1)])).status_code == 403


def test_errors_are_reported_row_by_row_and_nothing_is_saved(client, sign_in, college, db):  # noqa: F811
    sign_in(client, ["office"])
    rows = [
        _row(1),
        _row(2, programme="BSC"),
        _row(3, year="4Y"),
        _row(4, division="Z"),
        _row(5, phone="12345"),
        _row(6, dob="31-02-2007"),
        _row(1, name="Duplicate Prn"),
        _row(8, gender="X", category="NOPE"),
    ]
    report = _upload(client, _csv(rows)).json()
    assert report["status"] == "has_errors" and report["total"] == 8
    by_row = {(e["row"], e["field"]) for e in report["errors"]}
    assert {
        (3, "programme"),
        (4, "year"),
        (5, "division"),
        (6, "phone"),
        (7, "dob"),
        (8, "prn"),
        (9, "gender"),
        (9, "category"),
    } <= by_row
    assert not any(e["field"] == "programme_id" for e in report["errors"])  # one clear message per column
    assert db.students.count_documents({}) == 0 and db.users.count_documents({"kind": "student"}) == 0
    r = client.post(f"{API}/imports/{report['id']}/commit")
    assert r.status_code == 409


def test_missing_columns_and_bad_files(client, sign_in, college):  # noqa: F811
    sign_in(client, ["office"])
    r = _upload(client, _csv([["X"]], header=["name"]))
    assert r.status_code == 422 and "prn" in r.json()["error"]["message"]
    assert _upload(client, b"").status_code == 422
    assert _upload(client, b"PK\x03\x04 not really a workbook", "s.xlsx").status_code == 422


def test_clean_file_is_created_in_chunks(client, sign_in, college, db):  # noqa: F811
    sign_in(client, ["office"])
    report = _upload(client, _csv([_row(i) for i in range(1, 121)])).json()
    assert report["status"] == "validated" and report["valid"] == 120 and report["preview"][0]["prn"] == "2026BCA001"
    credentials, calls = [], 0
    while True:
        r = client.post(f"{API}/imports/{report['id']}/commit").json()
        calls += 1
        credentials += r["credentials"]
        if r["done"]:
            break
    assert calls == 3 and len(credentials) == 120 and r["committed"] == 120
    assert db.students.count_documents({}) == 120
    assert client.post(f"{API}/imports/{report['id']}/commit").json()["credentials"] == []  # nothing twice

    first = credentials[0]
    student = new_client(client)
    assert login(student, first["prn"], first["temporary_password"]).json()["must_change_password"] is True
    assert db.audit_log.count_documents({"action": "students.imported"}) == 120
    assert "temporary_password" not in str(db.imports.find_one())  # passwords are never stored

    again = _upload(client, _csv([_row(1)])).json()
    assert again["errors"][0]["message"] == "A student with this PRN already exists."


def test_another_user_cannot_run_my_import(client, sign_in, college):  # noqa: F811
    sign_in(client, ["office"])
    report = _upload(client, _csv([_row(1)])).json()
    other = new_client(client)
    sign_in(other, ["office"])
    assert other.post(f"{API}/imports/{report['id']}/commit").status_code == 404


def test_excel_files(client, sign_in, college, db):  # noqa: F811
    from openpyxl import Workbook

    sign_in(client, ["office"])
    wb = Workbook()
    ws = wb.active
    ws.append(["PRN*", "Full Name", "Programme", "Year", "Division", "Mobile", "Date of birth", "Category"])
    ws.append(["2026bca050", "Excel Student", "bca", 2, "a", 9876500050, datetime(2006, 7, 1), "obc"])
    buf = io.BytesIO()
    wb.save(buf)
    report = client.post(
        f"{API}/imports",
        files={"file": ("s.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()
    assert report["status"] == "validated", report["errors"]
    client.post(f"{API}/imports/{report['id']}/commit")
    s = db.students.find_one({"prn": "2026BCA050"})
    assert s["phone"] == "9876500050" and s["dob"] == "2006-07-01" and s["year_of_study"] == 2


def _current_year(db):
    now = datetime.now(UTC)
    return db.academic_years.insert_one(
        {
            "name": "2026-27",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "is_current": True,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    ).inserted_id


def test_promotion(client, sign_in, college, db):  # noqa: F811
    sign_in(client, ["office"])

    def create(prn, year):
        body = {
            "prn": prn,
            "name": f"Student {prn}",
            "programme_id": college["bca"],
            "year_of_study": year,
            "division_id": college["div"][year],
        }
        return client.post(API, json=body).json()["student"]["id"]

    fy = [create(f"2026BCA{i:03d}", 1) for i in range(1, 4)]
    ty = create("2024BCA001", 3)
    body = {"programme_id": college["bca"], "from_year": 1, "dry_run": True}
    assert client.post(f"{API}/promote", json=body).status_code == 409  # no current academic year yet
    _current_year(db)

    plan = client.post(f"{API}/promote", json={**body, "hold_back": [fy[2]]}).json()
    assert plan["counts"] == {"promoted": 2, "graduates": 0, "held_back": 1, "already_promoted": 0}
    assert db.students.count_documents({"year_of_study": 2}) == 0  # dry run changes nothing
    assert client.post(f"{API}/promote", json={**body, "dry_run": False}).status_code == 422  # reason required

    done = client.post(
        f"{API}/promote", json={**body, "hold_back": [fy[2]], "dry_run": False, "reason": "Results declared"}
    )
    assert done.status_code == 200
    moved = db.students.find_one({"_id": ObjectId(fy[0])})
    assert moved["year_of_study"] == 2 and str(moved["division_id"]) == college["div"][2]  # same division name
    assert db.students.find_one({"_id": ObjectId(fy[2])})["year_of_study"] == 1

    # Promoting SY now must not move the students just promoted from FY.
    sy = client.post(f"{API}/promote", json={"programme_id": college["bca"], "from_year": 2, "dry_run": True}).json()
    assert sy["counts"]["already_promoted"] == 2 and sy["counts"]["promoted"] == 0

    grads = client.post(
        f"{API}/promote",
        json={"programme_id": college["bca"], "from_year": 3, "dry_run": False, "reason": "Final results"},
    ).json()
    assert grads["counts"]["graduates"] == 1
    assert db.students.find_one({"_id": ObjectId(ty)})["status"] == "graduated"
    assert db.audit_log.count_documents({"action": "students.promoted"}) == 3
