from datetime import UTC, date, datetime, timedelta

from bson import ObjectId

from app.core import email
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1/notices"
PDF = b"%PDF-1.4\n" + b"x" * 100


def _office(client, sign_in):
    sign_in(client, ["office"], name="Sunil Gaikwad")
    return client


def _post(client, **kw):
    body = {
        "title": "Exam form deadline",
        "body": "Submit exam forms by Friday.",
        "audience": {"kind": "students"},
        **kw,
    }
    r = client.post(API, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_audiences(client, sign_in, fees, db):  # noqa: F811
    _office(client, sign_in)
    db.divisions.insert_one(
        {"programme_id": ObjectId(fees["bca"]), "year_of_study": 1, "name": "B", "status": "active"}
    )
    div_a = fees["div"][1]
    everyone = _post(client, title="College closed on Monday", audience={"kind": "everyone"})
    _post(client, title="All students: ID cards", audience={"kind": "students"})
    _post(client, title="Staff meeting", audience={"kind": "staff"})
    _post(
        client,
        title="BCA FY division A",
        audience={"kind": "class", "programme_id": fees["bca"], "year_of_study": 1, "division_id": div_a},
    )
    _post(client, title="BCA SY only", audience={"kind": "class", "programme_id": fees["bca"], "year_of_study": 2})
    assert everyone["audience_label"] == "Everyone"

    student = new_client(client)
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"division_id": ObjectId(div_a)}})
    sign_in_as_student(student, db, "2026BCA001")
    titles = {n["title"] for n in student.get(API).json()}
    assert titles == {"College closed on Monday", "All students: ID cards", "BCA FY division A"}

    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    assert {n["title"] for n in faculty.get(API).json()} == {"College closed on Monday", "Staff meeting"}
    assert faculty.post(API, json={"title": "Hello there", "audience": {"kind": "everyone"}}).status_code == 403

    staff_only = client.get(API, params={"manage": "true"}).json()
    assert len(staff_only) == 5  # publishers see everything to manage it
    hidden = next(n for n in staff_only if n["title"] == "Staff meeting")
    assert student.get(f"{API}/{hidden['id']}").status_code == 404


def test_schedule_expiry_pin_withdraw(client, sign_in, fees, db):  # noqa: F811
    _office(client, sign_in)
    later = _post(client, title="Results next week", publish_at=(datetime.now(UTC) + timedelta(days=2)).isoformat())
    assert later["state"] == "scheduled"
    old = _post(client, title="Old notice")
    db.notices.update_one({"_id": ObjectId(old["id"])}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(days=1)}})
    pinned = _post(client, title="Fee deadline", pinned=True)
    _post(client, title="Newest")
    bad = client.post(
        API,
        json={
            "title": "Bad dates",
            "audience": {"kind": "students"},
            "expires_on": (date.today() - timedelta(days=1)).isoformat(),
        },
    )
    assert bad.status_code == 422

    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    titles = [n["title"] for n in student.get(API).json()]
    assert titles == ["Fee deadline", "Newest"]  # pinned first; scheduled and expired hidden

    assert client.patch(f"{API}/{pinned['id']}", json={"status": "withdrawn"}).status_code == 422  # reason needed
    client.patch(f"{API}/{pinned['id']}", json={"status": "withdrawn", "reason": "Wrong date"})
    assert [n["title"] for n in student.get(API).json()] == ["Newest"]
    assert db.audit_log.find_one({"action": "notices.withdrawn"})["reason"] == "Wrong date"


def test_translations_search_and_attachment(client, sign_in, fees, db):  # noqa: F811
    _office(client, sign_in)
    n = _post(client, hi={"title": "परीक्षा फॉर्म", "body": "शुक्रवार तक"}, mr={"title": "परीक्षा अर्ज", "body": ""})
    assert n["hi"]["title"] == "परीक्षा फॉर्म" and n["mr"]["body"] == ""
    bad = client.post(
        f"{API}/{n['id']}/attachment", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 10, "image/png")}
    )
    assert bad.status_code == 415
    assert client.post(f"{API}/{n['id']}/attachment", files={"file": ("timetable.pdf", PDF, "application/pdf")}).json()[
        "has_attachment"
    ]

    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert [x["title"] for x in student.get(API, params={"q": "अर्ज"}).json()] == ["Exam form deadline"]
    assert student.get(f"{API}/{n['id']}/attachment").content == PDF
    assert student.get(f"{API}/{n['id']}").json()["body"] == "Submit exam forms by Friday."
    card = student.get("/api/v1/me/home").json()["cards"][-1]
    assert card["kind"] == "notice" and card["title"] == "Exam form deadline"


def test_email_in_chunks(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    from app.modules.notices import service

    monkeypatch.setattr(service, "EMAIL_CHUNK", 2)
    db.students.update_many({}, {"$set": {"email": "x@example.in"}})
    db.students.update_one({"prn": "2026BCA003"}, {"$unset": {"email": ""}})  # no email: skipped
    _office(client, sign_in)
    n = _post(client)
    email.OUTBOX.clear()
    first = client.post(f"{API}/{n['id']}/email").json()
    assert first == {"sent": 2, "failed": 0, "emailed": 2, "audience": 2, "remaining": 0, "done": True}
    assert "Exam form deadline" in email.OUTBOX[-1].subject
    again = client.post(f"{API}/{n['id']}/email").json()
    assert again["sent"] == 0 and again["done"] is True  # never twice
    later = _post(client, title="Later", publish_at=(datetime.now(UTC) + timedelta(days=1)).isoformat())
    assert client.post(f"{API}/{later['id']}/email").status_code == 409
