from datetime import UTC, date, datetime, timedelta

from bson import ObjectId

from app.core import email
from tests.admissions_fixtures import API, apply, cycle, fill, ready  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_students import college  # noqa: F401

RS = 100


def _structure(db, cycle):  # noqa: F811
    now = datetime.now(UTC)
    heads = [
        db.fee_heads.insert_one({"code": c, "name": c.title(), "status": "active", "created_at": now}).inserted_id
        for c in ("TUITION", "DEV")
    ]
    db.fee_structures.insert_one(
        {"academic_year_id": ObjectId(cycle["year"]), "programme_id": ObjectId(cycle["bca"]), "year_of_study": 1,
         "category_key": "*", "name": "BCA FY", "status": "active",
         "items": [{"head_id": heads[0], "amount": 20_000 * RS}, {"head_id": heads[1], "amount": 5_000 * RS}],
         "installments": [{"label": "Full", "due_date": str(date.today() + timedelta(days=30)), "amount": 25_000 * RS}],
         "late_fee": 0, "created_at": now}
    )  # fmt: skip


def _applicants(client, cycle, people):  # noqa: F811
    ids = {}
    for i, (name, category, percent) in enumerate(people):
        c = apply(client, cycle, f"98222{i:05d}", name=name, email_addr=f"{name.lower()}@example.com")
        a = fill(c, cycle, category=category, percent=percent)
        ready(cycle, c, a["id"])
        ids[name] = a["id"]
    return ids


def test_rounds_fill_open_then_reserved_seats(cycle, client, db):  # noqa: F811
    ids = _applicants(
        client,
        cycle,
        [
            ("Asha", "open", 90),
            ("Bilal", "obc", 88),
            ("Chetan", "open", 85),
            ("Deepa", "obc", 70),
            ("Esha", "open", 60),
            ("Farhan", "obc", 65),
        ],
    )
    cell = cycle["cell"]
    url = f"{API}/admissions/cycles/{cycle['cycle']['id']}/rounds"
    accept_by = (date.today() + timedelta(days=5)).isoformat()
    preview = cell.post(url, json={"programme_id": cycle["bca"], "accept_by": accept_by}).json()
    # Two open seats on merit alone (Bilal, OBC, wins one), then the OBC seat to the best remaining OBC.
    assert [(o["name"], o["seat_label"], o["rank"]) for o in preview["offers"]] == [
        ("Asha", "Open", 1),
        ("Bilal", "Open", 2),
        ("Deepa", "OBC reserved", 4),
    ]
    assert [w["name"] for w in preview["waiting"]] == ["Chetan", "Farhan", "Esha"]
    assert db.applications.count_documents({"status": "offered"}) == 0  # a preview changes nothing

    email.OUTBOX.clear()
    r1 = cell.post(url, json={"programme_id": cycle["bca"], "accept_by": accept_by, "dry_run": False}).json()
    assert r1["round"] == 1 and len(email.OUTBOX) == 3 and "offered admission" in email.OUTBOX[0].text
    assert cell.get(url, params={"programme_id": cycle["bca"]}).json()["seats"]["left"] == {"open": 0, cycle["obc"]: 0}

    # Deepa doesn't come by the date: her offer lapses and the OBC seat goes to Farhan in round 2.
    db.applications.update_one(
        {"_id": ObjectId(ids["Deepa"])}, {"$set": {"offer.accept_by": (date.today() - timedelta(days=1)).isoformat()}}
    )
    assert (
        cell.post(f"{API}/admissions/applications/{ids['Deepa']}/confirm", json={}).json()["error"]["code"] == "lapsed"
    )
    r2 = cell.post(url, json={"programme_id": cycle["bca"], "accept_by": accept_by, "dry_run": False}).json()
    assert r2["round"] == 2 and r2["lapsed"] == 1 and [o["name"] for o in r2["offers"]] == ["Farhan"]
    assert db.applications.find_one({"_id": ObjectId(ids["Deepa"])})["status"] == "lapsed"
    assert (
        cell.post(url, json={"programme_id": cycle["bca"], "accept_by": accept_by, "dry_run": False}).json()["error"][
            "code"
        ]
        == "nothing_to_offer"
    )


def test_confirm_creates_student_login_and_demand_then_cancel(cycle, client, db, sign_in):  # noqa: F811
    _structure(db, cycle)
    ids = _applicants(client, cycle, [("Asha", "open", 90)])
    cell = cycle["cell"]
    cell.post(
        f"{API}/admissions/cycles/{cycle['cycle']['id']}/rounds",
        json={
            "programme_id": cycle["bca"],
            "accept_by": (date.today() + timedelta(days=5)).isoformat(),
            "dry_run": False,
        },
    )
    email.OUTBOX.clear()
    done = cell.post(f"{API}/admissions/applications/{ids['Asha']}/confirm", json={"roll_no": "1"}).json()
    assert done["prn"] == "2026BCA001" and done["fee_demand"] == 25_000 * RS and done["warning"] is None
    assert "PRN: 2026BCA001" in email.OUTBOX[-1].text
    student = db.students.find_one({"prn": "2026BCA001"})
    assert (
        student["name"] == "Asha"
        and student["division_id"] == ObjectId(cycle["div"][1])
        and student["category_id"] == ObjectId(cycle["open"])
    )
    assert [d["status"] for d in student["documents"]] == ["verified", "verified"]
    assert db.files.find_one({"_id": student["documents"][0]["file_id"]})["student_id"] == student["_id"]
    assert cell.post(f"{API}/admissions/applications/{ids['Asha']}/confirm", json={}).status_code == 409  # once
    login = new_client(client).post(
        f"{API}/auth/login", json={"identifier": "2026BCA001", "password": done["temporary_password"]}
    )
    assert login.status_code == 200 and login.json()["must_change_password"]

    # She pays ₹10,000, then cancels 40 days before the course: 100% minus the ₹1,000 processing fee.
    accounts = new_client(client)
    sign_in(accounts, ["accounts"])
    accounts.post(
        f"{API}/fees/collect",
        json={
            "student_id": str(student["_id"]),
            "academic_year_id": cycle["year"],
            "amount": 10_000 * RS,
            "mode": "cash",
        },
    )
    quote = cell.get(f"{API}/admissions/applications/{ids['Asha']}/refund-quote").json()
    assert (quote["paid"], quote["percent"], quote["refundable"], quote["kept"]) == (
        10_000 * RS,
        100,
        9_000 * RS,
        1_000 * RS,
    )
    assert (
        cell.post(
            f"{API}/admissions/applications/{ids['Asha']}/cancel", json={"reason": "Joined another college"}
        ).json()["refundable"]
        == 9_000 * RS
    )
    balance = sum(e["amount"] for e in db.ledger_entries.find({"student_id": student["_id"]}))
    assert balance == -9_000 * RS  # a credit for Accounts to refund (with the Principal's approval)
    assert db.students.find_one({"_id": student["_id"]})["status"] == "cancelled"
    assert db.users.find_one({"_id": student["user_id"]})["read_only"] is True

    report = cell.get(f"{API}/admissions/cycles/{cycle['cycle']['id']}/report").json()["programmes"][0]
    assert (report["applied"], report["admitted"], report["cancelled"]) == (1, 0, 1)
    assert report["by_category"]["OPEN"] == {"applied": 1, "admitted": 0}
