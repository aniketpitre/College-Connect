from datetime import date, timedelta

import pytest

from tests.academics_fixtures import API, academics, college, make_timetable, slot  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

UT = [{"name": "Unit test 1", "max": 15}, {"name": "Unit test 2", "max": 15}, {"name": "Assignment", "max": 10}]


@pytest.fixture
def marks(academics, client, sign_in):  # noqa: F811
    office, s, t = academics["office"], academics["subjects"], academics["teachers"]
    tt = make_timetable(office, academics)
    office.post(f"{API}/timetables/{tt['id']}/slots", json=slot(s["BCA101"], [t["rao"]["id"]]))
    exam = new_client(client)
    sign_in(exam, ["exam_cell"])
    return {**academics, "exam": exam, "sheet": {"division_id": academics["div"][1], "subject_id": s["BCA101"]}}


def scheme(c, subject_id, components=UT, **extra):
    return c.put(f"{API}/marks/schemes", json={"subject_id": subject_id, "components": components, **extra})


def test_schemes(marks):
    t, s = marks["teachers"], marks["subjects"]
    assert scheme(t["rao"]["client"], s["BCA101"]).status_code == 403  # teachers don't set schemes
    assert scheme(t["comhod"]["client"], s["BCA101"]).status_code == 403  # other department
    bad = scheme(t["hod"]["client"], s["BCA101"], components=UT[:2])
    assert bad.status_code == 422 and "add up to 30" in bad.json()["error"]["message"]
    ok = scheme(t["hod"]["client"], s["BCA101"])
    assert ok.status_code == 200 and [c["key"] for c in ok.json()["components"]] == ["c1", "c2", "c3"]
    assert scheme(t["hod"]["client"], s["BCA101"], deadline="2026-09-30").status_code == 403  # Exam Cell sets it
    dl = scheme(marks["exam"], s["BCA101"], components=ok.json()["components"], deadline="2026-09-30")
    assert dl.json()["deadline"] == "2026-09-30" and dl.json()["components"][0]["key"] == "c1"
    # Renaming keeps keys; a new component gets a fresh key.
    renamed = [{**ok.json()["components"][0], "name": "Mid-term"}, {"name": "Quiz", "max": 25}]
    r = scheme(marks["exam"], s["BCA101"], components=renamed)
    assert [c["key"] for c in r.json()["components"]] == ["c1", "c4"]
    listing = (
        t["hod"]["client"].get(f"{API}/marks/schemes", params={"programme_id": marks["bca"], "semester": 1}).json()
    )
    assert {x["code"]: bool(x["scheme"]) for x in listing} == {"BCA101": True, "BCA102": False, "BCA103": False}


def test_marks_flow(monkeypatch, marks, client, db):
    at(monkeypatch, ist(date(2026, 9, 1), 10))
    t, s = marks["teachers"], marks["subjects"]
    rao, hod, exam = t["rao"]["client"], t["hod"]["client"], marks["exam"]
    r = rao.get(f"{API}/marks/sheet", params=marks["sheet"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_scheme"
    scheme(hod, s["BCA101"])
    mine = rao.get(f"{API}/marks/my-classes").json()
    assert [(x["class"], x["code"], x["status"]) for x in mine] == [("BCA FY A", "BCA101", "draft")]

    sheet = rao.get(f"{API}/marks/sheet", params=marks["sheet"]).json()
    assert len(sheet["students"]) == 3 and sheet["can_edit"] and not sheet["can_publish"]
    ids = {x["prn"]: x["id"] for x in sheet["students"]}
    put = lambda c, m, v: c.put(f"{API}/marks/sheet", json={**marks["sheet"], "marks": m, "base_version": v})  # noqa: E731
    assert put(rao, {ids["2026BCA001"]: {"c1": 16}}, 0).status_code == 422  # above 15
    assert put(rao, {ids["2026BCA001"]: {"c1": 12.3}}, 0).status_code == 422  # half marks only
    assert put(t["khan"]["client"], {}, 0).status_code == 403  # doesn't teach it
    saved = put(rao, {ids["2026BCA001"]: {"c1": 12.5, "c2": "AB", "c3": 9}, ids["2026BCA002"]: {"c1": 14}}, 0)
    assert saved.status_code == 200 and saved.json()["version"] == 1
    rows = {x["prn"]: x for x in saved.json()["students"]}
    assert rows["2026BCA001"]["total"] == 21.5 and rows["2026BCA002"]["total"] is None  # incomplete
    assert put(rao, {}, 0).json()["error"]["code"] == "marks_conflict"

    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert student.get(f"{API}/me/marks").json() == []  # not published yet
    act = lambda c, a, **k: c.post(f"{API}/marks/sheet/action", json={**marks["sheet"], "action": a, **k})  # noqa: E731
    assert act(hod, "approve").status_code == 403  # drafts aren't approved
    assert act(rao, "publish").json()["status"] == "published"
    mine = student.get(f"{API}/me/marks").json()
    assert mine[0]["total"] == 21.5 and [c["mark"] for c in mine[0]["components"]] == [12.5, "AB", 9]

    assert act(t["comhod"]["client"], "approve").status_code == 403
    assert act(hod, "approve").json()["status"] == "approved"
    assert put(rao, {ids["2026BCA003"]: {"c1": 10}}, 1).status_code == 409  # approved: no more changes
    assert act(hod, "return").status_code == 422  # needs a reason
    returned = act(hod, "return", reason="Neha's marks are missing")
    assert returned.json()["status"] == "draft" and returned.json()["returned_reason"] == "Neha's marks are missing"
    assert put(rao, {ids["2026BCA002"]: {"c2": 10, "c3": 8}}, 1).status_code == 200
    act(rao, "publish")
    act(hod, "approve")
    assert act(rao, "lock").status_code == 403
    assert act(exam, "lock").json()["status"] == "locked"
    assert act(exam, "unlock").status_code == 422
    assert act(exam, "unlock", reason="University asked for a correction").json()["status"] == "approved"
    assert db.audit_log.count_documents({"action": {"$regex": "^marks\\."}}) >= 10

    # Approved marks: the component maximums can't change any more.
    keys = [
        {"key": "c1", "name": "UT1", "max": 20},
        {"key": "c2", "name": "UT2", "max": 10},
        {"key": "c3", "name": "Assignment", "max": 10},
    ]
    r = scheme(exam, s["BCA101"], components=keys)
    assert r.status_code == 409, r.text


def test_deadline_closes_entry(monkeypatch, marks):
    from datetime import date

    s = marks["subjects"]
    scheme(marks["exam"], s["BCA101"], deadline="2026-09-30")
    rao = marks["teachers"]["rao"]["client"]
    at(monkeypatch, ist(date(2026, 9, 30), 18))
    assert rao.put(f"{API}/marks/sheet", json={**marks["sheet"], "marks": {}, "base_version": 0}).status_code == 200
    at(monkeypatch, ist(date(2026, 9, 30) + timedelta(days=1), 9))
    late = rao.put(f"{API}/marks/sheet", json={**marks["sheet"], "marks": {}, "base_version": 1})
    assert late.status_code == 403 and late.json()["error"]["code"] == "deadline_passed"
    assert rao.get(f"{API}/marks/sheet", params=marks["sheet"]).json()["deadline_passed"] is True
