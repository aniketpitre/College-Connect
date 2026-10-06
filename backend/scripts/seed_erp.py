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
    ("hod", "Dr. Sunita Rane", "hod@demo.college"),
    ("exam_cell", "Kiran Pathak", "exam@demo.college"),
    ("admission", "Nilesh Gawde", "admission@demo.college"),
]
# Other Computer Science teachers (they can sign in too, with the demo password).
TEACHERS = [
    "Anita Rao",
    "Imran Khan",
    "Kavita Shah",
    "Rahul Desai",
    "Swati Kale",
    "Nitin Bhave",
    "Farah Shaikh",
    "Ajay Naik",
]
SUBJECTS = {
    1: [("BCA101", "Programming in C", "theory"), ("BCA102", "Mathematics I", "theory"),
        ("BCA103", "Digital Electronics", "theory"), ("BCA104", "Communication Skills", "theory"),
        ("BCA105", "C Programming Lab", "practical")],
    3: [("BCA301", "Database Management Systems", "theory"), ("BCA302", "Data Structures", "theory"),
        ("BCA303", "Object-Oriented Programming", "theory"), ("BCA304", "Financial Accounting", "theory"),
        ("BCA305", "DBMS Lab", "practical")],
    5: [("BCA501", "Java Programming", "theory"), ("BCA502", "Web Technologies", "theory"),
        ("BCA503", "Software Engineering", "theory"), ("BCA504", "Python Programming", "theory"),
        ("BCA505", "Java Lab", "practical")],
}  # fmt: skip
PERIODS = [("09:00", "10:00"), ("10:00", "11:00"), ("11:15", "12:15"), ("12:15", "13:15")]
# day → subject index per period (4 = the practical, two hours, one batch at a time)
WEEK: dict[int, list[int | str]] = {
    1: [0, 1, 2, 3],
    2: [1, 2, 0, 3],
    3: [2, 0, "B1"],
    4: [3, 0, "B2"],
    5: [0, 1, 2, 3],
    6: [1, 2],
}
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
                "sid": f"seed-{user['_id']}-{token[:8]}",
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
                    "batch": f"B{n % 2 + 1}",
                    "roll_no": str(n),
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

    lectures = _seed_academics(app, db, rng, users, api, bca, year, divisions)
    exams = _seed_exams(app, db, rng, users, api, bca, divisions)
    certificates = _seed_certificates(app, db, api, divisions)
    parents = _seed_parents(db, api, divisions)
    applications = _seed_admissions(app, db, api, bca, year)

    for one in api.values():
        db.sessions.delete_one({"_id": one.token_id})
    _ = principal
    return {
        "staff accounts": len(users),
        "students": len(students),
        "receipts": receipts,
        "notices": 3,
        "timetables": 3,
        "lectures marked": lectures,
        "marks sheets": exams["sheets"],
        "exam forms": exams["forms"],
        "results": exams["results"],
        "certificate requests": certificates,
        "parent accounts": parents,
        "applications": applications,
    }


def _seed_academics(
    app: Any,
    db: Database[dict[str, Any]],
    rng: random.Random,
    users: dict[str, dict[str, Any]],
    api: dict[str, "_Api"],
    bca: dict[str, Any],
    year: dict[str, Any],
    divisions: dict[int, str],
) -> int:
    """Subjects, teachers, the term-1 timetable of each class and three weeks of attendance."""
    admin, office, hod = api["system_admin"], api["office"], api["hod"]
    dept = bca["department_id"]
    from bson import ObjectId

    teacher_ids = [users["faculty"]["_id"]]
    for name in TEACHERS:
        email = f"{name.split()[0].lower()}@demo.college"
        user = db.users.find_one({"email": email}) or repo.create_user(
            kind="staff",
            name=name,
            email=email,
            roles=["faculty"],
            password_hash=hash_password(DEMO_PASSWORD),
            must_change_password=False,
            created_by=None,
        )
        teacher_ids.append(user["_id"])
    db.users.update_many(
        {"_id": {"$in": [*teacher_ids, users["hod"]["_id"]]}}, {"$set": {"department_id": ObjectId(dept)}}
    )

    start = date.fromisoformat(year["start_date"])
    term_end = date(start.year, 11, 30)
    marked = 0
    for y, sem in ((1, 1), (2, 3), (3, 5)):
        subject_ids = []
        for code, name, kind in SUBJECTS[sem]:
            internal = 40 if kind == "theory" else 50
            body = {
                "programme_id": bca["id"],
                "semester": sem,
                "code": code,
                "name": name,
                "credits": 4,
                "type": kind,
                "max_internal": internal,
                "max_external": 100 - internal,
            }
            subject_ids.append(admin.call("POST", "/setup/subjects", json=body)["id"])
        tt = office.call(
            "POST",
            "/timetables",
            json={
                "academic_year_id": year["id"],
                "division_id": divisions[y],
                "term": 1,
                "valid_from": start.isoformat(),
                "valid_to": term_end.isoformat(),
            },
        )
        # Three teachers per class: no teacher has two classes at once.
        t = [str(x) for x in teacher_ids[(y - 1) * 3 : y * 3]]
        teacher_of = {0: t[0], 1: t[1], 2: t[2], 3: t[1], 4: t[0]}
        for weekday, plan in WEEK.items():
            for i, item in enumerate(plan):
                practical = isinstance(item, str)  # practical batch: periods 3–4 together
                subject = 4 if practical else int(item)
                slot = {
                    "day": weekday,
                    "start": PERIODS[2 if practical else i][0],
                    "end": PERIODS[3 if practical else i][1],
                    "subject_id": subject_ids[subject],
                    "faculty_ids": [teacher_of[subject]],
                    "room": f"LAB{y}" if practical else f"10{y}",
                    "batch": item if practical else None,
                }
                office.call("POST", f"/timetables/{tt['id']}/slots", json=slot)

        # Past attendance, marked by the HOD (who may mark any lecture of the department).
        absence = {}
        for st in db.students.find({"division_id": ObjectId(divisions[y])}, {"_id": 1}):
            roll = rng.random()
            absence[str(st["_id"])] = (
                rng.uniform(0.3, 0.45)
                if roll < 0.1
                else rng.uniform(0.12, 0.25)
                if roll < 0.3
                else rng.uniform(0.0, 0.1)
            )
        first = max(start, date.today() - timedelta(days=21))
        day = first
        while day < date.today():
            if day.isoweekday() != 7:
                week = hod.call("GET", "/timetable/week", params={"division_id": divisions[y], "day": day.isoformat()})
                lectures = next(d for d in week["days"] if d["date"] == day.isoformat())["lectures"]
                for lec in lectures:
                    sheet = hod.call(
                        "GET", "/attendance/sheet", params={"slot_id": lec["slot_id"], "day": day.isoformat()}
                    )
                    absent = [x["id"] for x in sheet["students"] if rng.random() < absence[x["id"]]]
                    hod.call(
                        "PUT",
                        "/attendance/sheet",
                        json={"slot_id": lec["slot_id"], "date": day.isoformat(), "absent": absent},
                    )
                    marked += 1
            day += timedelta(days=1)
    _ = app
    return marked


def _seed_exams(
    app: Any,
    db: Database[dict[str, Any]],
    rng: random.Random,
    users: dict[str, dict[str, Any]],
    api: dict[str, "_Api"],
    bca: dict[str, Any],
    divisions: dict[int, str],
) -> dict[str, int]:
    """Schemes for every subject, marks in different states, an open exam and last year's results."""
    from bson import ObjectId

    exam, hod = api["exam_cell"], api["hod"]
    today = date.today()
    subjects = list(db.subjects.find({"programme_id": ObjectId(bca["id"])}).sort("code", 1))
    for s in subjects:
        parts = (
            [{"name": "Unit test 1", "max": 15}, {"name": "Unit test 2", "max": 15}, {"name": "Assignment", "max": 10}]
            if s["type"] == "theory"
            else [{"name": "Journal", "max": 20}, {"name": "Practical exam", "max": 30}]
        )
        exam.call(
            "PUT",
            "/marks/schemes",
            json={
                "subject_id": str(s["_id"]),
                "components": parts,
                "deadline": (today + timedelta(days=20)).isoformat(),
            },
        )

    # The first FY teacher enters marks: one subject approved, one published but incomplete.
    teacher = api["faculty"]
    fy = {x["code"]: str(x["_id"]) for x in subjects if x["semester"] == 1}
    sheets = 0
    for code, complete in (("BCA101", True), ("BCA105", False)):
        sheet = teacher.call("GET", "/marks/sheet", params={"division_id": divisions[1], "subject_id": fy[code]})
        marks: dict[str, dict[str, Any]] = {}
        for n, st in enumerate(sheet["students"]):
            if not complete and n % 7 == 3:
                continue  # left blank: the Upload Guard lists these
            entry: dict[str, Any] = {}
            for c in sheet["scheme"]["components"]:
                entry[c["key"]] = "AB" if rng.random() < 0.03 else round(rng.uniform(0.45, 0.95) * c["max"] * 2) / 2
            marks[st["id"]] = entry
        teacher.call(
            "PUT",
            "/marks/sheet",
            json={"division_id": divisions[1], "subject_id": fy[code], "marks": marks, "base_version": 0},
        )
        teacher.call(
            "POST",
            "/marks/sheet/action",
            json={"division_id": divisions[1], "subject_id": fy[code], "action": "publish"},
        )
        if complete:
            hod.call(
                "POST",
                "/marks/sheet/action",
                json={"division_id": divisions[1], "subject_id": fy[code], "action": "approve"},
            )
        sheets += 1

    # Last year's results for SY (semester 1 papers), published, with a few backlogs.
    last = exam.call(
        "POST",
        "/exams/sessions",
        json={"name": "Oct-Nov exams (last year, FY sem 1)", "term": 1, "kind": "university",
              "classes": [{"programme_id": bca["id"], "year_of_study": 2}],
              "form_deadline": (today - timedelta(days=300)).isoformat(), "fee_head_code": None},
    )  # fmt: skip
    grades = ["O", "A+", "A", "B+", "B", "C", "P", "F"]
    rows = ["PRN,Subject code,Internal,External,Total,Grade,Credits"]
    for st in db.students.find({"division_id": ObjectId(divisions[2])}, {"prn": 1}).sort("prn", 1):
        for code in sorted(fy):
            grade = rng.choices(grades, weights=[8, 14, 20, 20, 16, 10, 6, 6])[0]
            internal = rng.randint(22, 38)
            external = rng.randint(12, 24) if grade == "F" else rng.randint(28, 58)
            rows.append(f"{st['prn']},{code},{internal},{external},{internal + external},{grade},4")
    files = {"file": ("results.csv", "\n".join(rows).encode(), "text/csv")}
    exam.call("POST", f"/exams/sessions/{last['id']}/results/import", params={"dry_run": False}, files=files)
    exam.call("POST", f"/exams/sessions/{last['id']}/results/publish", json={"publish": True, "revaluation_days": 15})
    results = len(rows) - 1

    # This term's university exam for FY: open, with half the class's forms in.
    now = exam.call(
        "POST",
        "/exams/sessions",
        json={"name": "Oct-Nov university exams", "term": 1, "kind": "university",
              "classes": [{"programme_id": bca["id"], "year_of_study": y} for y in (1, 2, 3)],
              "form_deadline": (today + timedelta(days=10)).isoformat(), "fee_head_code": "EXAM", "seat_prefix": "C"},
    )  # fmt: skip
    first = today + timedelta(days=35)
    papers = [
        {
            "subject_id": str(s["_id"]),
            "date": (first + timedelta(days=2 * i)).isoformat(),
            "start": "10:00",
            "end": "13:00",
        }
        for i, s in enumerate(x for x in subjects if x["semester"] == 1)
    ]
    exam.call("PATCH", f"/exams/sessions/{now['id']}", json={"papers": papers})
    forms = 0
    for st in db.students.find({"division_id": ObjectId(divisions[1])}).sort("prn", 1).limit(10):
        user = db.users.find_one({"_id": st["user_id"]})
        assert user is not None
        student_api = _Api(app, db, user)
        db.users.update_one({"_id": user["_id"]}, {"$set": {"onboarded_at": datetime.now(UTC)}})
        student_api.call("POST", f"/me/exams/{now['id']}/form")
        db.sessions.delete_one({"_id": student_api.token_id})
        db.users.update_one({"_id": user["_id"]}, {"$unset": {"onboarded_at": ""}})
        forms += 1
    return {"sheets": sheets, "forms": forms, "results": results}


def _seed_certificates(
    app: Any, db: Database[dict[str, Any]], api: dict[str, "_Api"], divisions: dict[int, str]
) -> int:
    """A few certificate requests in every state, so the office queue and dashboards have something to show."""
    from bson import ObjectId

    office = api["office"]
    plan = [
        ("bonafide", "Bank education loan", ["verify", "sign", "issue"]),
        ("character", "Scholarship application", []),
        ("fee_paid", "Income tax return of parent", ["verify"]),
        ("bonafide", "Passport application", []),
    ]
    students = list(db.students.find({"division_id": ObjectId(divisions[1])}).sort("prn", 1).skip(1).limit(len(plan)))
    for st, (kind, purpose, steps) in zip(students, plan, strict=True):
        user = db.users.find_one({"_id": st["user_id"]})
        assert user is not None
        student_api = _Api(app, db, user)
        db.users.update_one({"_id": user["_id"]}, {"$set": {"onboarded_at": datetime.now(UTC)}})
        req = student_api.call("POST", "/me/certificates", json={"type": kind, "purpose": purpose})
        db.sessions.delete_one({"_id": student_api.token_id})
        db.users.update_one({"_id": user["_id"]}, {"$unset": {"onboarded_at": ""}})
        for step in steps:
            office.call("POST", f"/certificates/requests/{req['id']}/action", json={"action": step})
    # One request is past its promised date, as the Principal's dashboard would show it.
    db.certificate_requests.update_one(
        {"purpose": "Passport application"}, {"$set": {"due_date": (date.today() - timedelta(days=1)).isoformat()}}
    )
    return len(plan)


PARENT_PHONE = "9876500001"


def _seed_parents(db: Database[dict[str, Any]], api: dict[str, "_Api"], divisions: dict[int, str]) -> int:
    """One parent with two children (FY and SY roll 1), who can also sign in with the demo password."""
    from bson import ObjectId

    for year in (1, 2):
        st = db.students.find_one({"division_id": ObjectId(divisions[year])}, sort=[("prn", 1)])
        assert st is not None
        api["office"].call(
            "POST",
            f"/students/{st['_id']}/parents",
            json={"name": "Demo Parent", "phone": PARENT_PHONE, "email": "parent@demo.college", "relation": "Father",
                  "consent": True},
        )  # fmt: skip
    db.users.update_one(
        {"phone": PARENT_PHONE, "kind": "parent"}, {"$set": {"password_hash": hash_password(DEMO_PASSWORD)}}
    )
    return 1


APPLICANTS = [  # name, category, HSC %, how far they got
    ("Ananya Kulkarni", "OPEN", 91.4, "verified"),
    ("Rahul Jadhav", "OBC", 84.0, "verified"),
    ("Mehul Shah", "OPEN", 78.6, "verified"),
    ("Sana Shaikh", "OBC", 72.2, "submitted"),
    ("Vikram Pawar", "OPEN", 65.0, "draft"),
]
PDF = b"%PDF-1.4\n% demo marksheet\n"


def _seed_admissions(
    app: Any, db: Database[dict[str, Any]], api: dict[str, "_Api"], bca: dict[str, Any], year: dict[str, Any]
) -> int:
    """An open admission for BCA with applicants at every stage, and two call-back enquiries."""
    cell = api["admission"]
    cats = {c["code"]: str(c["_id"]) for c in db.categories.find({})}
    today = date.today()
    body = {
        "name": f"Admissions {year['name']}",
        "academic_year_id": year["id"],
        "apply_until": (today + timedelta(days=15)).isoformat(),
        "course_start": (today + timedelta(days=30)).isoformat(),
        "application_fee": 300 * 100,
        "programmes": [{"programme_id": bca["id"], "year_of_study": 1, "seats": 10, "reserved": {cats["OBC"]: 2}}],
    }
    cycle = cell.call("POST", "/admissions/cycles", json=body)
    cell.call("PUT", f"/admissions/cycles/{cycle['id']}", json={**body, "status": "open"})
    public = TestClient(app, base_url="https://seed.local", headers={"X-Requested-With": "seed"})
    for i, (name, cat, percent, stage) in enumerate(APPLICANTS):
        phone = f"97000000{i:02d}"
        email = name.split()[0].lower() + "@example.com"
        r = public.post(
            "/api/v1/apply/start", json={"cycle_id": cycle["id"], "name": name, "phone": phone, "email": email}
        )
        assert r.status_code == 200, r.text
        user = db.users.find_one({"phone": phone, "kind": "applicant"})
        assert user is not None
        me = _Api(app, db, user)
        born = int(year["name"][:4]) - 18
        me.call(
            "PUT",
            "/me/application",
            json={
                "programme_id": bca["id"],
                "dob": f"{born}-0{i + 1}-15",
                "gender": "female" if i % 2 == 0 else "male",
                "category_id": cats[cat],
                "address": {"city": "Pune", "district": "Pune", "pincode": "411001"},
                "previous_education": {
                    "exam": "HSC",
                    "board": "Maharashtra State Board",
                    "year": born + 18,
                    "percentage": percent,
                },
            },
        )
        for doc in ("ssc_marksheet", "hsc_marksheet"):
            me.call(
                "POST",
                "/me/application/documents",
                data={"type": doc},
                files={"file": (f"{doc}.pdf", PDF, "application/pdf")},
            )
        if stage != "draft":
            a = me.call("GET", "/me/application")
            cell.call("POST", f"/admissions/applications/{a['id']}/fee", json={"mode": "cash"})
            me.call("POST", "/me/application/submit")
            if stage == "verified":
                for d in a["documents"]:
                    cell.call(
                        "POST", f"/admissions/applications/{a['id']}/documents/{d['id']}/decide", json={"approve": True}
                    )
                cell.call("POST", f"/admissions/applications/{a['id']}/decide", json={"action": "verify"})
        db.sessions.delete_one({"_id": me.token_id})
    for name, phone, note in (("Farhan Khan", "9822000011", "Is there a hostel?"), ("Isha More", "9822000012", "")):
        cell.call(
            "POST",
            "/admissions/enquiries",
            json={"name": name, "phone": phone, "programme_id": bca["id"], "message": note, "source": "phone"},
        )
    return len(APPLICANTS)
