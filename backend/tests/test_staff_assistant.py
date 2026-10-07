"""Staff assistant (plan 5.8): pre-defined, permission-checked queries; the AI only picks one."""

from app.modules.assistant import staff
from app.rag import generator
from app.rag.generator import StaffPlan
from tests.fees_fixtures import RS, college, fees, new_client  # noqa: F401
from tests.test_fees_collect import _collect, _ready
from tests.test_students import sign_in_as_student

API = "/api/v1/assistant/staff"


def test_questions_become_queries(db, fees):  # noqa: F811
    p = staff.parse("How many SY BCA students owe more than ₹10,000?")
    assert (p.tool, p.programme, p.year, p.min_amount, p.overdue_only) == (
        "fees_outstanding",
        "BCA",
        2,
        10_000 * RS,
        False,
    )
    p = staff.parse("Which FY students have overdue fees above Rs 5k?")
    assert (p.tool, p.year, p.min_amount, p.overdue_only) == ("fees_outstanding", 1, 5_000 * RS, True)
    p = staff.parse("Who is below 75% attendance in BCA FY A?")
    assert (p.tool, p.below, p.programme, p.year, p.division) == ("attendance_below", 75.0, "BCA", 1, "A")
    p = staff.parse("Which bonafide certificate requests are past the promised date?")
    assert (p.tool, p.cert_type, p.overdue_only) == ("certificates_pending", "bonafide", True)
    assert staff.parse("Which TY students have backlogs?").tool == "backlogs"
    assert staff.parse("What is the weather today?").tool is None


def test_fees_query_with_numbers_and_the_list(client, sign_in, fees, db):  # noqa: F811
    accounts = new_client(client)
    _ready(accounts, sign_in, fees)
    assert _collect(accounts, fees, prn="2026BCA001", amount=10_000 * RS).status_code == 201
    r = accounts.post(API, json={"question": "How many FY BCA students owe more than ₹20,000?"}).json()
    assert r["answered"] and r["query"] == "fees_outstanding" and r["count"] == 2
    assert [x["prn"] for x in r["rows"]] == ["2026BCA002", "2026BCA003"]
    assert (
        r["summary"].startswith("2 BCA FY students have fees outstanding above ₹20,000.00")
        and "₹52,000.00" in r["summary"]
    )
    assert r["filters"] == {"programme": "BCA", "year": 1, "above": "₹20,000.00"}
    assert [c["key"] for c in r["columns"]] == ["prn", "student", "class", "balance", "overdue"]
    everyone = accounts.post(API, json={"question": "Which students have fees pending?"}).json()
    assert everyone["count"] == 3
    log = db.audit_log.find_one({"action": "assistant.staff_query"}, sort=[("at", 1)])
    assert log["details"]["query"] == "fees_outstanding" and log["details"]["count"] == 2

    unknown = accounts.post(API, json={"question": "What is the weather today?"}).json()
    assert unknown["answered"] is False and unknown["examples"]
    bad = accounts.post(API, json={"question": "Who owes fees in BSC year 1?"})
    assert bad.status_code == 200  # "bsc" is not a programme code here: the whole college


def test_permissions_are_checked(client, sign_in, fees, db):  # noqa: F811
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    r = faculty.post(API, json={"question": "How many students owe more than ₹10,000?"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert faculty.post(API, json={"question": "Which certificate requests are pending?"}).status_code == 403
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert student.post(API, json={"question": "How many students owe fees?"}).status_code == 403

    office = new_client(client)
    sign_in(office, ["office"])
    student.post("/api/v1/me/certificates", json={"type": "bonafide", "purpose": "Bank account"})
    r = office.post(API, json={"question": "Which bonafide certificate requests are open?"}).json()
    assert r["count"] == 1 and r["rows"][0]["prn"] == "2026BCA001"
    assert (
        office.post(API, json={"question": "Which certificate requests are past the promised date?"}).json()["count"]
        == 0
    )
    assert office.post(API, json={"question": "Which FY students have backlogs?"}).json()["count"] == 0
    low = office.post(API, json={"question": "Who is below 75% attendance in BCA FY?"}).json()
    assert low["query"] == "attendance_below" and low["count"] == 0 and "below 75%" in low["summary"]


def test_the_ai_only_picks_the_query(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    accounts = new_client(client)
    _ready(accounts, sign_in, fees)
    monkeypatch.setattr(generator, "llm_available", lambda: True)
    monkeypatch.setattr(
        generator,
        "plan_staff_query",
        lambda q: StaffPlan(tool="fees_outstanding", programme="BCA", year=1, min_amount_rupees=25_000),
    )
    r = accounts.post(API, json={"question": "पहिल्या वर्षाच्या BCA मध्ये ₹25,000 पेक्षा जास्त कोणाचे शुल्क बाकी आहे?"}).json()
    assert r["query"] == "fees_outstanding" and r["count"] == 3 and r["filters"]["above"] == "₹25,000.00"
