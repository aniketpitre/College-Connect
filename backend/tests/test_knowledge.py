"""Knowledge base in MongoDB, notices indexed for their own audience, automatic translation (plan 5.1-5.3)."""

import io
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.rag import generator, store
from app.rag.generator import GeneratedAnswer, NoticeTranslation
from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_parents import _otp_sign_in
from tests.test_students import sign_in_as_student

API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean_kb(db):
    """Other test modules use the bundled index: leave no knowledge base behind."""
    yield
    for name in ("kb_meta", "kb_documents", "kb_chunks", "notices"):
        db[name].delete_many({})
    store._cached.update(version=None, index=None)


def _ask(c, question, language="en", **kw):
    r = c.post(f"{API}/assistant/ask", json={"question": question, "language": language, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _public(_c, question):
    """What applicants (and anything marked public) can be answered from: the public-only filter."""
    from app.rag.pipeline import answer_question

    return answer_question(question, "en", None, store.public_only())


def _titles(result):
    return {s["title"] for s in result["sources"]}


def _office(client, sign_in):
    office = new_client(client)
    sign_in(office, ["office"], name="Sunil Gaikwad")
    return office


def test_documents_bootstrap_upload_audience_and_removal(client, sign_in, fees, db):  # noqa: F811
    office = _office(client, sign_in)
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert student.get(f"{API}/kb/documents").status_code == 403

    listing = office.get(f"{API}/kb/documents").json()  # the first look copies the bundled documents in
    bundled = [d for d in listing["documents"] if d["source"] == "bundled"]
    assert len(bundled) == 6 and all(d["audience"] == "public" for d in bundled)
    assert listing["status"]["retrieval"] == "bm25" and listing["status"]["chunks_total"] > 0
    assert _public(client, "What's the hostel fee?")["sources"][0]["section"] == "Section 2: Hostel Fees"

    md = b"# Sports\n\n## Gymkhana timings\nThe gymkhana is open from 6 am to 9 pm on all working days.\n"
    r = office.post(
        f"{API}/kb/documents",
        data={"title": "Sports Committee Circular", "category": "notices", "audience": "public"},
        files={"file": ("sports.md", md, "text/markdown")},
    )
    assert r.status_code == 201, r.text
    sports = r.json()
    assert sports["chunks"] == 2 and sports["source"] == "upload"
    hit = _public(client, "When is the gymkhana open?")
    assert hit["grounded"] and hit["sources"][0]["title"] == "Sports Committee Circular"

    inside = office.post(
        f"{API}/kb/documents",
        data={
            "title": "Eduroam wireless",
            "category": "hostel",
            "audience": "everyone",
            "text": "## Eduroam\nEduroam login uses your PRN and the passphrase from the library desk.",
        },
    ).json()
    assert "Eduroam wireless" not in _titles(_public(client, "How do I log in to eduroam?"))  # members only
    assert _titles(_ask(student, "How do I log in to eduroam?")) == {"Eduroam wireless"}

    bad = office.post(
        f"{API}/kb/documents",
        data={"title": "Scan", "category": "fees", "audience": "public"},
        files={"file": ("scan.docx", b"x", "application/octet-stream")},
    )
    assert bad.status_code == 415
    assert office.post(f"{API}/kb/documents", data={"title": "Empty", "category": "fees"}).status_code == 422

    assert office.delete(f"{API}/kb/documents/{sports['id']}").json() == {"ok": True}
    assert "Sports Committee Circular" not in _titles(_public(client, "When is the gymkhana open?"))
    assert office.delete(f"{API}/kb/documents/{inside['id']}").status_code == 200
    assert db.audit_log.count_documents({"action": {"$in": ["kb.document_added", "kb.document_removed"]}}) == 4
    assert office.post(f"{API}/kb/reindex").json() == {"notices": 0, "embedded": 0, "remaining": 0}


def test_notices_answer_only_their_audience_until_expiry(client, sign_in, fees, db):  # noqa: F811
    office = _office(client, sign_in)
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")  # BCA first year
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])

    def post(title, body, audience, **kw):
        r = office.post(f"{API}/notices", json={"title": title, "body": body, "audience": audience, **kw})
        assert r.status_code == 201, r.text
        return r.json()

    fy = post(
        "FY BCA practical batches",
        "Practical batches for the lab start on Monday 12 October.",
        {"kind": "class", "programme_id": fees["bca"], "year_of_study": 1},
    )
    post(
        "SY BCA industrial visit",
        "The industrial visit to Pune leaves on 20 October.",
        {"kind": "class", "programme_id": fees["bca"], "year_of_study": 2},
    )
    post("Staff meeting", "The staff meeting on accreditation is on Thursday in the seminar hall.", {"kind": "staff"})

    mine = _ask(student, "When do practical batches for the lab start?")
    assert mine["grounded"] and mine["sources"][0]["link"] == f"/app/notices/{fy['id']}"
    assert "SY BCA industrial visit" not in _titles(_ask(student, "When does the industrial visit to Pune leave?"))
    assert "Staff meeting" not in _titles(_ask(student, "When is the staff meeting on accreditation?"))
    assert "Staff meeting" in _titles(_ask(faculty, "When is the staff meeting on accreditation?"))
    assert "SY BCA industrial visit" not in _titles(_ask(faculty, "When does the industrial visit to Pune leave?"))
    assert "FY BCA practical batches" not in _titles(_public(client, "When do practical batches for the lab start?"))

    # Public notices answer on the public help desk; a class notice can't be public.
    assert (
        office.post(
            f"{API}/notices", json={"title": "Class only", "audience": {"kind": "staff"}, "public": True}
        ).status_code
        == 422
    )
    post(
        "Convocation ceremony",
        "The convocation ceremony is on 15 November at 10 am in the auditorium.",
        {"kind": "everyone"},
        public=True,
    )
    assert _titles(_public(client, "When is the convocation ceremony?")) == {"Convocation ceremony"}

    # Withdrawn: gone at once. Expired: gone from the next day, with no job.
    office.patch(f"{API}/notices/{fy['id']}", json={"status": "withdrawn", "reason": "Wrong date"})
    assert "FY BCA practical batches" not in _titles(_ask(student, "When do practical batches for the lab start?"))
    assert db.kb_documents.count_documents({"notice_id": ObjectId(fy["id"])}) == 0
    db.kb_chunks.update_many(
        {"title": "Convocation ceremony"}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(minutes=1)}}
    )
    store._cached.update(version=None)
    assert "Convocation ceremony" not in _titles(_public(client, "When is the convocation ceremony?"))
    later = post(
        "Annual sports day",
        "Annual sports day is on 1 December.",
        {"kind": "students"},
        publish_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    assert later["state"] == "scheduled" and "Annual sports day" not in _titles(
        _ask(student, "When is the annual sports day?")
    )

    # An office notice can't be removed from the knowledge base page: withdraw it instead.
    doc = db.kb_documents.find_one({"source": "notice", "title": "Staff meeting"})
    assert office.delete(f"{API}/kb/documents/{doc['_id']}").status_code == 409


def test_pdf_notice_parent_and_applicant(client, sign_in, fees, db):  # noqa: F811
    from pypdf import PdfWriter

    office = _office(client, sign_in)
    n = office.post(f"{API}/notices", json={"title": "Exam form circular", "audience": {"kind": "students"}}).json()
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.write(buf)
    files = {"file": ("circular.pdf", buf.getvalue(), "application/pdf")}
    assert office.post(f"{API}/notices/{n['id']}/attachment", files=files).status_code == 200
    doc = db.kb_documents.find_one({"notice_id": ObjectId(n["id"])})
    assert doc and doc["chunks"] == 1  # a scanned PDF has no text: the title still answers

    # A parent asks for their child: the child's notices.
    body = {
        "name": "Suresh Patil",
        "phone": "9876500001",
        "email": "suresh@example.com",
        "relation": "Father",
        "consent": True,
    }
    rohan = fees["students"]["2026BCA001"]
    assert office.post(f"{API}/students/{rohan}/parents", json=body).status_code == 201
    parent = _otp_sign_in(client)
    r = parent.post(f"{API}/assistant/ask", json={"question": "exam form circular"}, headers={"X-Child": rohan})
    assert r.status_code == 200 and _titles(r.json()) == {"Exam form circular"}


def test_automatic_translation(client, sign_in, fees, db, monkeypatch):  # noqa: F811
    office = _office(client, sign_in)
    off = office.post(f"{API}/notices/translate", json={"title": "Holiday", "body": "Closed on Monday."})
    assert off.status_code == 503 and off.json()["error"]["code"] == "not_configured"

    monkeypatch.setattr(generator, "llm_available", lambda: True)
    calls = []

    def fake_translate(title, body):
        calls.append(title)
        return NoticeTranslation(
            hi_title="छुट्टी", hi_body="सोमवार को कॉलेज बंद रहेगा।", mr_title="सुट्टी", mr_body="सोमवारी महाविद्यालय बंद राहील."
        )

    monkeypatch.setattr(generator, "translate_notice", fake_translate)
    drafts = office.post(f"{API}/notices/translate", json={"title": "Holiday", "body": "Closed on Monday."}).json()
    assert drafts["hi"]["title"] == "छुट्टी" and drafts["mr"]["body"].startswith("सोमवारी")
    too_long = office.post(f"{API}/notices/translate", json={"title": "Long", "body": "x" * 6001})
    assert too_long.status_code == 422

    # Published without translations: filled in after the response, marked as automatic, indexed.
    n = office.post(
        f"{API}/notices",
        json={
            "title": "Holiday on Monday",
            "body": "The college is closed on Monday.",
            "audience": {"kind": "everyone"},
        },
    ).json()
    saved = db.notices.find_one({"_id": ObjectId(n["id"])})
    assert saved["hi"]["machine"] and saved["mr"]["title"] == "सुट्टी"
    sections = set(db.kb_chunks.distinct("section", {"title": "Holiday on Monday"}))
    assert sections == {"Notice", "हिंदी", "मराठी"}
    assert db.audit_log.find_one({"action": "notices.translated"})["details"]["languages"] == ["hi", "mr"]

    # Staff typed their own: kept, and never overwritten.
    calls.clear()
    typed = office.post(
        f"{API}/notices",
        json={
            "title": "Fee camp",
            "body": "Fee camp on Tuesday.",
            "audience": {"kind": "students"},
            "hi": {"title": "शुल्क शिविर", "body": "मंगलवार को"},
            "mr": {"title": "शुल्क शिबिर", "body": "मंगळवारी"},
        },
    ).json()
    assert calls == [] and typed["hi"] == {"title": "शुल्क शिविर", "body": "मंगलवार को"}
    office.patch(f"{API}/notices/{n['id']}", json={"hi": {"title": "अवकाश", "body": "सोमवार को अवकाश"}})
    assert "machine" not in db.notices.find_one({"_id": ObjectId(n["id"])})["hi"]

    # Answerable in Marathi: the question is translated for the search, the answer cites the notice.
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    monkeypatch.setattr(generator, "translate_query_to_english", lambda q: "Is the college closed on Monday?")

    def fake_answer(question, language, chunks):
        return GeneratedAnswer(
            answer="हो, सोमवारी महाविद्यालय बंद आहे.", answerable=True, cited_chunk_ids=[chunks[0]["id"]]
        )

    monkeypatch.setattr(generator, "generate_answer", fake_answer)
    answer = _ask(student, "सोमवारी कॉलेज बंद आहे का?", "mr")
    assert answer["grounded"] and _titles(answer) == {"Holiday on Monday"} and answer["language"] == "mr"


def test_daily_catch_up_indexes_older_notices(client, sign_in, fees, db):  # noqa: F811
    from app.modules.knowledge import service as knowledge

    now = datetime.now(UTC)
    nid = db.notices.insert_one(
        {
            "title": "Library hours",
            "body": "The library is open till 8 pm during exams.",
            "audience": {"kind": "everyone"},
            "publish_at": now,
            "expires_at": None,
            "status": "published",
            "created_at": now,
        }
    ).inserted_id
    assert knowledge.catch_up()["notices"] == 1
    assert db.notices.find_one({"_id": nid})["kb_indexed_at"]
    assert knowledge.catch_up()["notices"] == 0
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert _titles(_ask(student, "How late is the library open during exams?")) == {"Library hours"}
    assert db.queries.find_one({"channel": "portal"}) is not None
    assert "user_id" not in db.queries.find_one({"channel": "portal"})


def test_applicants_get_public_documents_only(client, sign_in, fees, db):  # noqa: F811
    office = _office(client, sign_in)
    office.post(
        f"{API}/notices",
        json={
            "title": "Exam form circular",
            "body": "Exam forms close on 30 October.",
            "audience": {"kind": "everyone"},
        },
    )
    applicant = new_client(client)
    sign_in(applicant, ["applicant"], kind="applicant", email="applicant@example.com")
    assert "Exam form circular" not in _titles(_ask(applicant, "When do exam forms close?"))
    assert (
        _ask(applicant, "What documents do I need for admission?")["sources"][0]["section"]
        == "Section 3: Required Documents"
    )
