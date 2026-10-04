"""Shared set-up for fee tests: BCA, the current academic year, fee heads and three FY students."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.test_students import college  # noqa: F401 - pytest fixture

RS = 100  # paise per rupee


def new_client(client):
    return TestClient(client.app, base_url="https://testserver", headers={"X-Requested-With": "x"})


@pytest.fixture
def fees(db, college, client, sign_in):  # noqa: F811
    now = datetime.now(UTC)
    year = db.academic_years.insert_one(
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
    heads = {
        code: db.fee_heads.insert_one({"code": code, "name": name, "status": "active", "created_at": now}).inserted_id
        for code, name in (("TUITION", "Tuition fee"), ("DEV", "Development fee"), ("EXAM", "Examination fee"))
    }
    office = new_client(client)
    sign_in(office, ["office"])
    ids = {}
    for prn, name, cat in (
        ("2026BCA001", "Rohan Patil", "open"),
        ("2026BCA002", "Neha Joshi", "obc"),
        ("2026BCA003", "Om Shinde", "open"),
    ):
        r = office.post(
            "/api/v1/students",
            json={
                "prn": prn,
                "name": name,
                "programme_id": college["bca"],
                "year_of_study": 1,
                "category_id": college[cat],
            },
        )
        ids[prn] = r.json()["student"]["id"]
    return {"year": str(year), "heads": {k: str(v) for k, v in heads.items()}, "students": ids, **college}


def structure_body(fees, *, category=None, tuition=20_000, dev=5_000, exam=1_000, due_first=None):
    """₹ amounts → a structure body in paise with two installments."""
    total = (tuition + dev + exam) * RS
    first = date.today() + timedelta(days=30) if due_first is None else due_first
    return {
        "academic_year_id": fees["year"],
        "programme_id": fees["bca"],
        "year_of_study": 1,
        "category_id": category,
        "name": "BCA FY 2026-27" + (" (category)" if category else ""),
        "items": [
            {"head_id": fees["heads"]["TUITION"], "amount": tuition * RS},
            {"head_id": fees["heads"]["DEV"], "amount": dev * RS},
            {"head_id": fees["heads"]["EXAM"], "amount": exam * RS},
        ],
        "installments": [
            {"label": "First installment", "due_date": first.isoformat(), "amount": total - total // 2},
            {
                "label": "Second installment",
                "due_date": (first + timedelta(days=120)).isoformat(),
                "amount": total // 2,
            },
        ],
        "late_fee": 100 * RS,
    }
