"""Shared set-up for timetable and attendance tests: the current year, BCA subjects, teachers
with departments, a second department, and three FY students in division A."""

from datetime import UTC, date, datetime, timedelta

import pytest

from tests.fees_fixtures import new_client
from tests.test_students import college  # noqa: F401 - pytest fixture

API = "/api/v1"
MONDAY = date(2026, 7, 6)
assert MONDAY.isoweekday() == 1


@pytest.fixture
def academics(db, college, client, sign_in):  # noqa: F811
    now = datetime.now(UTC)
    meta = {"status": "active", "created_at": now, "updated_at": now}
    year = db.academic_years.insert_one(
        {"name": "2026-27", "start_date": "2026-06-15", "end_date": "2027-04-30", "is_current": True, **meta}
    ).inserted_id
    bca = college["bca"]
    from bson import ObjectId

    bca_id = ObjectId(bca)
    cs = db.programmes.find_one({"_id": bca_id})["department_id"]
    subjects = {}
    for code, name, sem, kind in (
        ("BCA101", "Programming in C", 1, "theory"),
        ("BCA102", "Mathematics I", 1, "theory"),
        ("BCA103", "C Lab", 1, "practical"),
        ("BCA301", "Databases", 3, "theory"),
    ):
        subjects[code] = str(
            db.subjects.insert_one(
                {
                    "programme_id": bca_id,
                    "semester": sem,
                    "code": code,
                    "name": name,
                    "credits": 4,
                    "type": kind,
                    "max_internal": 40,
                    "max_external": 60,
                    **meta,
                }
            ).inserted_id
        )
    commerce = db.departments.insert_one({"code": "COM", "name": "Commerce", **meta}).inserted_id
    bcom = db.programmes.insert_one(
        {
            "code": "BCOM",
            "name": "Bachelor of Commerce",
            "department_id": commerce,
            "level": "UG",
            "duration_years": 3,
            "semesters_per_year": 2,
            "year_labels": ["FY", "SY", "TY"],
            **meta,
        }
    ).inserted_id
    bcom_div = db.divisions.insert_one({"programme_id": bcom, "year_of_study": 1, "name": "A", **meta}).inserted_id
    bcom_sub = db.subjects.insert_one(
        {
            "programme_id": bcom,
            "semester": 1,
            "code": "COM101",
            "name": "Accounts",
            "credits": 4,
            "type": "theory",
            "max_internal": 40,
            "max_external": 60,
            **meta,
        }
    ).inserted_id

    teachers = {}
    for key, name, roles, dept in (
        ("rao", "Anita Rao", ["faculty"], cs),
        ("khan", "Imran Khan", ["faculty"], cs),
        ("hod", "Dr. Mehta", ["hod"], cs),
        ("comhod", "Dr. Iyer", ["hod"], commerce),
    ):
        c = new_client(client)
        user = sign_in(c, roles, name=name)
        db.users.update_one({"_id": user["_id"]}, {"$set": {"department_id": dept}})
        teachers[key] = {"client": c, "id": str(user["_id"])}

    office = new_client(client)
    sign_in(office, ["office"])
    students = {}
    for prn, name in (("2026BCA001", "Rohan Patil"), ("2026BCA002", "Neha Joshi"), ("2026BCA003", "Om Shinde")):
        r = office.post(
            f"{API}/students",
            json={
                "prn": prn,
                "name": name,
                "programme_id": bca,
                "year_of_study": 1,
                "division_id": college["div"][1],
                "category_id": college["open"],
            },
        )
        assert r.status_code == 201, r.text
        students[prn] = r.json()["student"]["id"]
    return {
        **college,
        "year": str(year),
        "subjects": subjects,
        "bcom_div": str(bcom_div),
        "bcom_subject": str(bcom_sub),
        "teachers": teachers,
        "office": office,
        "students": students,
    }


def make_timetable(client, academics, *, division=None, term=1, valid_from="2026-06-15", valid_to="2026-11-15"):
    r = client.post(
        f"{API}/timetables",
        json={
            "academic_year_id": academics["year"],
            "division_id": division or academics["div"][1],
            "term": term,
            "valid_from": valid_from,
            "valid_to": valid_to,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def slot(subject, faculty, day=1, start="09:00", end="10:00", room="", batch=None):
    return {
        "day": day,
        "start": start,
        "end": end,
        "subject_id": subject,
        "faculty_ids": faculty,
        "room": room,
        "batch": batch,
    }


def week_dates():
    return [MONDAY + timedelta(days=i) for i in range(6)]
