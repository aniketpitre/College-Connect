"""
ERP demo data: BCA with 60 students across three years, fees, payments, a pending concession
and a few notices, plus one demo account per staff role. Run through `python -m scripts.seed_demo
--erp` (which refuses the production database).

Everything goes through the real API (in-process), so the data obeys the same rules as data
entered by hand: ledger entries, gap-free receipts and the audit log.
"""

import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from pymongo.database import Database

from app.core.security import hash_password, new_token, token_hash
from app.main import create_app
from app.modules.users import repo

DEMO_PASSWORD = "Demo@CollegeConnect2026"  # noqa: S105 - demo databases only; seed_demo refuses production
STAFF = [
    ("system_admin", "Asha Kulkarni", "admin@demo.college"),
    ("principal", "Dr. Vivek Deshmukh", "principal@demo.college"),
    ("office", "Sunil Gaikwad", "office@demo.college"),
    ("accounts", "Meera Joshi", "accounts@demo.college"),
    ("faculty", "Prakash More", "faculty@demo.college"),
]
MALE = ["Rohan", "Om", "Aditya", "Kunal", "Sahil", "Yash", "Tejas", "Omkar", "Pratik", "Sairaj"]
FEMALE = ["Neha", "Priya", "Sneha", "Pooja", "Anjali", "Rutuja", "Shruti", "Komal", "Vaishnavi", "Gauri"]
LAST = ["Patil", "Joshi", "Shinde", "Kulkarni", "Pawar", "Jadhav", "Deshpande", "More", "Chavan", "Bhosale"]
FEES = {1: (22_000, 4_000, 1_500), 2: (24_000, 4_000, 1_500), 3: (26_000, 4_000, 2_000)}  # tuition, dev, exam (₹)


class _Api:
    def __init__(self, app: Any, db: Database[dict[str, Any]], user: dict[str, Any]) -> None:
        self.client = TestClient(app, base_url="https://seed.local", headers={"X-Requested-With": "seed"})
        token = new_token()
        now = datetime.now(UTC)
        db.sessions.insert_one(
            {
                "_id": token_hash(token),
                "sid": f"seed-{user['_id']}",
                "user_id": user["_id"],
                "state": "active",
                "created_at": now,
                "last_seen_at": now,
                "expires_at": now + timedelta(hours=1),
            }
        )
        self.client.cookies.set("cc_session", token)
        self.token_id = token_hash(token)

    def call(self, method: str, path: str, **kwargs: Any) -> Any:
        r = self.client.request(method, f"/api/v1{path}", **kwargs)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} → {r.status_code}: {r.text}")
        return r.json()


def seed(db: Database[dict[str, Any]], rng: random.Random) -> dict[str, int]:
    if db.students.count_documents({}):
        raise SystemExit("This database already has students. Use a fresh database for the ERP demo.")
    app = create_app()
    users = {}
    for role, name, email in STAFF:
        users[role] = db.users.find_one({"email": email}) or repo.create_user(
            kind="staff",
            name=name,
            email=email,
            roles=[role],
            password_hash=hash_password(DEMO_PASSWORD),
            must_change_password=False,
            created_by=None,
        )
    api = {role: _Api(app, db, u) for role, u in users.items()}
    admin, office, accounts, principal = api["system_admin"], api["office"], api["accounts"], api["principal"]

    admin.call("POST", "/setup/starter-data")
    setup = admin.call("GET", "/setup")
    bca = next(p for p in setup["programmes"] if p["code"] == "BCA")
    year = next(y for y in setup["academic_years"] if y["is_current"])
    divisions = {d["year_of_study"]: d["id"] for d in setup["divisions"] if d["programme_id"] == bca["id"]}
    categories = [c["id"] for c in setup["categories"]]

    accounts.call("POST", "/fees/heads/starter")
    heads = {h["code"]: h["id"] for h in accounts.call("GET", "/fees/heads")}
    start = date.fromisoformat(year["start_date"])
    for y, (tuition, dev, exam) in FEES.items():
        total = (tuition + dev + exam) * 100
        first_due = start + timedelta(days=45)
        accounts.call(
            "POST",
            "/fees/structures",
            json={
                "academic_year_id": year["id"],
                "programme_id": bca["id"],
                "year_of_study": y,
                "category_id": None,
                "name": f"BCA {['FY', 'SY', 'TY'][y - 1]} {year['name']}",
                "items": [
                    {"head_id": heads["TUITION"], "amount": tuition * 100},
                    {"head_id": heads["DEV"], "amount": dev * 100},
                    {"head_id": heads["EXAM"], "amount": exam * 100},
                ],
                "installments": [
                    {"label": "First installment", "due_date": first_due.isoformat(), "amount": total - total // 2},
                    {
                        "label": "Second installment",
                        "due_date": (first_due + timedelta(days=150)).isoformat(),
                        "amount": total // 2,
                    },
                ],
                "late_fee": 100 * 100,
            },
        )

    students: list[dict[str, Any]] = []
    for y in (1, 2, 3):
        batch = start.year - (y - 1)
        for n in range(1, 21):
            gender = rng.choice(["male", "female"])
            name = f"{rng.choice(MALE if gender == 'male' else FEMALE)} {rng.choice(LAST)}"
            body = office.call(
                "POST",
                "/students",
                json={
                    "prn": f"{batch}BCA{n:03d}",
                    "name": name,
                    "programme_id": bca["id"],
                    "year_of_study": y,
                    "division_id": divisions[y],
                    "category_id": rng.choice(categories),
                    "gender": gender,
                    "dob": f"{batch - 18}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                    "phone": f"9{rng.randint(100000000, 999999999)}",
                    "guardian": {"name": f"{rng.choice(MALE)} {name.split()[1]}", "relation": "Father"},
                },
            )
            students.append(body["student"])
    # Demo students sign in with the demo password (the real flow gives a temporary one).
    db.users.update_many(
        {"kind": "student", "prn": {"$in": [s["prn"] for s in students]}},
        {"$set": {"password_hash": hash_password(DEMO_PASSWORD), "must_change_password": False}},
    )
    for y in (1, 2, 3):
        accounts.call(
            "POST",
            "/fees/demands/generate",
            json={"academic_year_id": year["id"], "programme_id": bca["id"], "year_of_study": y, "dry_run": False},
        )

    receipts = 0
    for s in students:
        roll = rng.random()
        if roll < 0.15:
            continue  # nothing paid yet
        tuition, dev, exam = FEES[s["year_of_study"]]
        total = (tuition + dev + exam) * 100
        amounts = [total] if roll > 0.75 else [total - total // 2] if roll > 0.35 else [rng.randint(20, 80) * 10_000]
        for amount in amounts:
            mode = rng.choice(["cash", "upi", "upi"])
            accounts.call(
                "POST",
                "/fees/collect",
                json={
                    "student_id": s["id"],
                    "academic_year_id": year["id"],
                    "amount": amount,
                    "mode": mode,
                    "reference": f"UPI{rng.randint(10**11, 10**12 - 1)}" if mode == "upi" else "",
                },
            )
            receipts += 1
    accounts.call(
        "POST",
        "/fees/concessions",
        json={
            "student_id": students[5]["id"],
            "academic_year_id": year["id"],
            "head_id": heads["TUITION"],
            "amount": 5_000 * 100,
            "kind": "merit",
            "reason": "University topper in FY (demo)",
        },
    )

    today = date.today()
    for title, body_text, audience, pinned in (
        (
            "Exam form deadline",
            "Fill the semester exam form on the university portal by the 20th. Late forms carry a fine.",
            {"kind": "students"},
            True,
        ),
        (
            "Practical batches for FY BCA",
            "Practical batches are on the notice board outside the computer lab.",
            {"kind": "class", "programme_id": bca["id"], "year_of_study": 1},
            False,
        ),
        ("Staff meeting on Saturday", "All staff meet in the seminar hall at 11 am.", {"kind": "staff"}, False),
    ):
        office.call(
            "POST",
            "/notices",
            json={
                "title": title,
                "body": body_text,
                "audience": audience,
                "pinned": pinned,
                "expires_on": (today + timedelta(days=30)).isoformat(),
            },
        )

    for one in api.values():
        db.sessions.delete_one({"_id": one.token_id})
    _ = principal
    return {"staff accounts": len(users), "students": len(students), "receipts": receipts, "notices": 3}
