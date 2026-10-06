import re
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core import email
from tests.fees_fixtures import new_client
from tests.test_students import college  # noqa: F401

API = "/api/v1"
PDF = b"%PDF-1.4\n%test\n"


@pytest.fixture
def cycle(db, college, client, sign_in):  # noqa: F811
    now = datetime.now(UTC)
    dates = {"start_date": "2026-06-15", "end_date": "2027-04-30"}
    year = db.academic_years.insert_one(
        {"name": "2026-27", **dates, "is_current": True, "status": "active", "created_at": now, "updated_at": now}
    ).inserted_id
    cell = new_client(client)
    sign_in(cell, ["admission"], name="Kiran Kale")
    body = {
        "name": "Admissions 2026-27",
        "academic_year_id": str(year),
        "apply_until": (date.today() + timedelta(days=20)).isoformat(),
        "course_start": (date.today() + timedelta(days=40)).isoformat(),
        "application_fee": 500 * 100,
        "programmes": [
            {"programme_id": college["bca"], "year_of_study": 1, "seats": 3, "reserved": {college["obc"]: 1}}
        ],
    }
    r = cell.post(f"{API}/admissions/cycles", json=body)
    assert r.status_code == 201, r.text
    c = r.json()
    cell.put(f"{API}/admissions/cycles/{c['id']}", json={**body, "status": "open"})
    return {**college, "cell": cell, "cycle": c, "year": str(year), "body": body}


def apply(client, cycle, phone, name="Asha Pawar", email_addr="asha@example.com"):
    """Starts an application and signs the applicant in with the emailed code."""
    c = new_client(client)
    email.OUTBOX.clear()
    r = c.post(
        f"{API}/apply/start", json={"cycle_id": cycle["cycle"]["id"], "name": name, "phone": phone, "email": email_addr}
    )
    assert r.status_code == 200, r.text
    code = re.search(r"\b(\d{6})\b", email.OUTBOX[-1].subject).group(1)
    assert c.post(f"{API}/apply/verify", json={"phone": phone, "code": code}).json()["kind"] == "applicant"
    return c


def fill(c, cycle, *, category="open", percent=82.5, dob="2008-05-01"):
    r = c.put(
        f"{API}/me/application",
        json={
            "programme_id": cycle["bca"],
            "dob": dob,
            "gender": "female",
            "category_id": cycle[category],
            "previous_education": {"exam": "HSC", "board": "Maharashtra", "year": 2026, "percentage": percent},
        },
    )
    assert r.status_code == 200, r.text
    for t in ("ssc_marksheet", "hsc_marksheet"):
        c.post(
            f"{API}/me/application/documents", data={"type": t}, files={"file": (f"{t}.pdf", PDF, "application/pdf")}
        )
    return c.get(f"{API}/me/application").json()


def ready(cycle, c, app_id):
    """Fee at the counter, submit, verify documents and the application (as the Admission Cell)."""
    cell = cycle["cell"]
    cell.post(f"{API}/admissions/applications/{app_id}/fee", json={"mode": "cash"})
    assert c.post(f"{API}/me/application/submit").status_code == 200
    a = cell.get(f"{API}/admissions/applications/{app_id}").json()
    for d in a["documents"]:
        cell.post(f"{API}/admissions/applications/{app_id}/documents/{d['id']}/decide", json={"approve": True})
    r = cell.post(f"{API}/admissions/applications/{app_id}/decide", json={"action": "verify"})
    assert r.json()["status"] == "verified", r.text
