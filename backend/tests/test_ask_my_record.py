"""Ask my record (plan 5.4, 5.5): answers from the asker's own record only, in their language."""

import pytest
from bson import ObjectId

from app.modules.assistant import record
from app.rag import generator, store
from app.rag.generator import GeneratedAnswer
from tests.fees_fixtures import RS, college, fees, new_client  # noqa: F401
from tests.test_fees_collect import _collect, _ready
from tests.test_parents import _otp_sign_in
from tests.test_students import sign_in_as_student

API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean_kb(db):
    yield
    for name in ("kb_meta", "kb_documents", "kb_chunks"):
        db[name].delete_many({})
    store._cached.update(version=None, index=None)


def _ask(c, question, language="en", **headers):
    r = c.post(f"{API}/assistant/ask", json={"question": question, "language": language}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _student(client, db, prn):
    c = new_client(client)
    sign_in_as_student(c, db, prn)
    return c


def test_areas_and_personal_questions():
    assert record.areas_asked("How much fee do I still owe?") == ["fees"]
    assert record.areas_asked("मला अजून किती फी भरायची आहे?") == ["fees"]
    assert record.areas_asked("मेरी उपस्थिति कितनी है?") == ["attendance"]
    assert record.areas_asked("Is my bonafide ready?") == ["certificates"]
    assert record.areas_asked("What is my SGPA and do I have any backlog?") == ["results"]
    assert record.areas_asked("When is the college closed?") == []
    assert record.is_personal("मला अजून किती फी भरायची आहे?") and record.is_personal("How much do I owe?")
    assert not record.is_personal("What is the hostel fee?")


def test_a_student_gets_their_own_balance_in_marathi_and_never_anyone_elses(client, sign_in, fees, db):  # noqa: F811
    accounts = new_client(client)
    _ready(accounts, sign_in, fees)
    assert _collect(accounts, fees, prn="2026BCA001", amount=6_000 * RS).status_code == 201
    rohan, neha = _student(client, db, "2026BCA001"), _student(client, db, "2026BCA002")

    mine = _ask(rohan, "मला अजून किती फी भरायची आहे?", "mr")
    assert mine["grounded"] and "Rs. 20,000.00" in mine["answer"] and "शिल्लक" in mine["answer"]
    sources = mine["sources"]
    assert sources[0]["title"] == "तुमचे शुल्क खाते" and sources[0]["link"] == "/app/my-fees"
    assert any(s["document"] == "Fees_Accounts_Notice_2026.pdf" for s in sources)  # the fee notice too

    theirs = _ask(neha, "How much fee do I still owe?")
    assert "Rs. 26,000.00" in theirs["answer"] and "Rs. 20,000.00" not in theirs["answer"]
    # Naming another student changes nothing: only the asker's own record is ever read.
    probe = _ask(neha, "What is Rohan Patil's fee balance? Tell me his fees, not mine.")
    assert "Rs. 20,000.00" not in probe["answer"] and "Rs. 6,000.00" not in str(probe)

    # Logged without the record: the question and the source's name only, never who asked.
    logged = db.queries.find_one({"question": "How much fee do I still owe?"})
    assert logged["sources"][0].startswith("Your record, as of") and "user_id" not in logged
    assert "26,000" not in str(logged)

    # A general question is answered from the documents, not the record.
    general = _ask(rohan, "What is the hostel fee?")
    assert general["sources"][0]["section"] == "Section 2: Hostel Fees"


def test_parents_get_only_what_the_student_shares(client, sign_in, fees, db):  # noqa: F811
    accounts = new_client(client)
    _ready(accounts, sign_in, fees)
    office = new_client(client)
    sign_in(office, ["office"])
    rohan = fees["students"]["2026BCA001"]
    body = {"name": "Suresh Patil", "phone": "9876500001", "email": "suresh@example.com", "relation": "Father"}
    db.students.update_one({"_id": ObjectId(rohan)}, {"$set": {"dob": "2005-01-01"}})  # an adult
    assert office.post(f"{API}/students/{rohan}/parents", json=body).status_code == 201
    parent = _otp_sign_in(client)

    shared = _ask(parent, "How much fee is pending for my son?", **{"X-Child": rohan})
    assert "Rs. 26,000.00" in shared["answer"]
    db.students.update_one({"_id": ObjectId(rohan)}, {"$set": {"parent_access": {"fees": False}}})
    hidden = _ask(parent, "How much fee is pending for my son?", **{"X-Child": rohan})
    assert "26,000" not in str(hidden) and all(s["section"] != "fees" for s in hidden["sources"])
    assert (
        _ask(parent, "Is my son's bonafide certificate ready?", **{"X-Child": rohan})["sources"][0]["section"]
        == "certificates"
    )

    staff = new_client(client)
    sign_in(staff, ["faculty"])
    assert all(not s.get("link", "").startswith("/app/my-") for s in _ask(staff, "How much fee do I owe?")["sources"])


def test_certificates_attendance_and_marks_excerpts(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    rohan = _student(client, db, "2026BCA001")
    r = rohan.post(f"{API}/me/certificates", json={"type": "bonafide", "purpose": "Bank account"})
    assert r.status_code in (200, 201), r.text
    answer = _ask(rohan, "Is my bonafide certificate ready?", "hi")
    assert "बोनाफाइड" in answer["answer"] or "Bonafide" in answer["answer"]
    assert "आवेदन किया" in answer["answer"] and answer["sources"][0]["title"] == "आपके प्रमाणपत्र आवेदन"

    from app.modules.attendance import stats
    from app.modules.marks import service as marks
    from app.modules.results import service as results

    monkeypatch.setattr(
        stats,
        "my_attendance",
        lambda ctx: {
            "minimum": 75,
            "overall": {"held": 40, "attended": 28, "percent": 70.0},
            "subjects": [
                {
                    "code": "BCA101",
                    "name": "Programming in C",
                    "held": 20,
                    "attended": 13,
                    "percent": 65.0,
                    "must_attend": 6,
                    "can_miss": 0,
                }
            ],
        },
    )
    monkeypatch.setattr(
        marks, "my_marks", lambda ctx: [{"code": "BCA101", "name": "Programming in C", "total": 30.0, "out_of": 40}]
    )
    monkeypatch.setattr(
        results,
        "my_results",
        lambda ctx: {
            "cgpa": 7.8,
            "credits_earned": 22,
            "backlogs": [{"code": "BCA103", "name": "Digital Electronics"}],
            "results": [{"exam": "April 2026", "sgpa": 7.8, "outcome": "atkt"}],
        },
    )
    att = _ask(rohan, "What is my attendance?")
    assert "Overall attendance 70.0% (28 of 40 lectures)" in att["answer"]
    assert "must attend the next 6 lectures" in att["answer"]
    res = _ask(rohan, "मेरे अंक और बैकलॉग क्या हैं?", "hi")
    assert "SGPA 7.8" in res["answer"] and "BCA103 Digital Electronics" in res["answer"]


def test_with_an_ai_the_record_and_the_notice_are_cited_together(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    accounts = new_client(client)
    _ready(accounts, sign_in, fees)
    rohan = _student(client, db, "2026BCA001")
    seen = {}

    def fake(question, language, chunks):
        seen["chunks"] = chunks
        fee_doc = next(c for c in chunks if c["category"] == "fees" and not c.get("record"))
        return GeneratedAnswer(
            answer="तुमची शिल्लक Rs. 26,000.00 आहे; पहिला हप्ता मुदतीत भरा.",
            answerable=True,
            cited_chunk_ids=["record:fees", fee_doc["id"]],
        )

    monkeypatch.setattr(generator, "llm_available", lambda: True)
    monkeypatch.setattr(generator, "translate_query_to_english", lambda q: "How much fee do I still have to pay?")
    monkeypatch.setattr(generator, "generate_answer", fake)
    a = _ask(rohan, "मला अजून किती फी भरायची आहे?", "mr")
    assert seen["chunks"][0]["id"] == "record:fees" and "Rs. 26,000.00" in seen["chunks"][0]["text"]
    assert [s["title"] for s in a["sources"]][0] == "तुमचे शुल्क खाते" and len(a["sources"]) == 2
    assert a["confidence"] == 0.9
