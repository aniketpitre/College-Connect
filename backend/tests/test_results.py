import io
from datetime import date

from pypdf import PdfReader

from tests.academics_fixtures import API, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist
from tests.test_students import sign_in_as_student

HEADER = "PRN,Subject code,Internal,External,Total,Grade,Credits\n"
GOOD = HEADER + "\n".join(
    [
        "2026BCA001,BCA101,30,52,82,A,4",
        "2026BCA001,BCA102,28,45,73,B+,4",
        "2026BCA001,BCA103,45,48,93,O,4",
        "2026BCA002,BCA101,32,50,82,A,4",
        "2026BCA002,BCA102,20,10,30,F,4",
        "2026BCA002,BCA103,40,25,65,B,4",
        "2026BCA003,BCA101,,,,AB,4",
        "2026BCA003,BCA102,,,,AB,4",
        "2026BCA003,BCA103,,,,AB,4",
    ]
)


def test_results_import_publish_cgpa_backlogs_revaluation(monkeypatch, academics, client, db, sign_in):  # noqa: F811
    at(monkeypatch, ist(date(2026, 12, 20), 11))
    exam = new_client(client)
    sign_in(exam, ["exam_cell"])
    body = {"name": "Oct-Nov 2026", "term": 1, "classes": [{"programme_id": academics["bca"], "year_of_study": 1}],
            "form_deadline": "2026-10-10", "fee_head_code": None}  # fmt: skip
    sid = exam.post(f"{API}/exams/sessions", json=body).json()["id"]
    upload = lambda data, dry: exam.post(  # noqa: E731
        f"{API}/exams/sessions/{sid}/results/import",
        params={"dry_run": dry},
        files={"file": ("r.csv", data.encode(), "text/csv")},
    ).json()

    bad = upload(GOOD + "\n2026BCA999,BCA101,1,1,2,P,4\n2026BCA001,COM101,1,1,1,P,4", True)
    assert not bad["imported"] and len(bad["problems"]) == 2
    assert upload(GOOD + "\n2026BCA999,BCA101,1,1,2,P,4", False)["imported"] is False  # problems block the import
    preview = upload(GOOD, True)
    assert preview == {"rows": 9, "students": 3, "pass": 1, "atkt": 1, "problems": [], "imported": False}
    assert upload(GOOD, False)["imported"] is True

    students = {}
    for prn in academics["students"]:
        c = new_client(client)
        sign_in_as_student(c, db, prn)
        students[prn] = c
    assert students["2026BCA001"].get(f"{API}/me/results").json()["results"] == []  # not published yet
    assert exam.post(f"{API}/exams/sessions/{sid}/results/publish", json={"publish": True}).json()["published"]
    summary = exam.get(f"{API}/exams/sessions/{sid}/results").json()
    assert summary["counts"] == {"pass": 1, "atkt": 1, "absent": 1}

    rohan = students["2026BCA001"].get(f"{API}/me/results").json()
    assert rohan["results"][0]["sgpa"] == 8.33 and rohan["cgpa"] == 8.33 and rohan["backlogs"] == []
    neha = students["2026BCA002"].get(f"{API}/me/results").json()
    assert neha["results"][0]["outcome"] == "atkt" and neha["results"][0]["sgpa"] == 4.67
    assert [b["code"] for b in neha["backlogs"]] == ["BCA102"]

    # The backlog goes onto the next exam form.
    body2 = {**body, "name": "Apr-May 2027", "term": 2, "form_deadline": "2027-03-31"}
    sid2 = exam.post(f"{API}/exams/sessions", json=body2).json()["id"]
    form = next(x for x in students["2026BCA002"].get(f"{API}/me/exams").json() if x["id"] == sid2)
    assert [s["code"] for s in form["subjects"] if s.get("backlog")] == ["BCA102"]

    # Revaluation: Neha asks once; the university changes the grade to P.
    rid = neha["results"][0]["id"]
    asked = students["2026BCA002"].post(f"{API}/me/results/{rid}/revaluation", json={"code": "BCA102"})
    assert asked.status_code == 200
    assert (
        students["2026BCA002"].post(f"{API}/me/results/{rid}/revaluation", json={"code": "BCA102"}).status_code == 409
    )
    assert (
        students["2026BCA001"].post(f"{API}/me/results/{rid}/revaluation", json={"code": "BCA102"}).status_code == 404
    )
    reval = exam.get(f"{API}/results/revaluations", params={"status": "requested"}).json()[0]
    assert reval["prn"] == "2026BCA002" and reval["old"]["grade"] == "F"
    decided = exam.post(
        f"{API}/results/revaluations/{reval['id']}/decide",
        json={"status": "changed", "external": 22, "total": 42, "grade": "P"},
    )
    assert decided.json()["status"] == "changed"
    neha = students["2026BCA002"].get(f"{API}/me/results").json()
    assert neha["backlogs"] == [] and neha["results"][-1]["outcome"] == "pass" and neha["results"][-1]["sgpa"] == 6.0
    paper = next(s for s in neha["results"][-1]["subjects"] if s["code"] == "BCA102")
    assert paper["revaluation"]["status"] == "changed" and paper["total"] == 42

    # Statement PDF; the revaluation window closes.
    pdf = students["2026BCA001"].get(f"{API}/me/results/{rohan['results'][0]['id']}.pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "STATEMENT OF RESULT" in text and "SGPA 8.33" in text and "Result: PASS" in text
    at(monkeypatch, ist(date(2027, 1, 15), 11))
    late = students["2026BCA001"].post(
        f"{API}/me/results/{rohan['results'][0]['id']}/revaluation", json={"code": "BCA101"}
    )
    assert late.json()["error"]["code"] == "closed"

    # Withdrawing hides them again; only the Exam Cell imports and publishes.
    assert (
        academics["office"].post(f"{API}/exams/sessions/{sid}/results/publish", json={"publish": False}).status_code
        == 403
    )
    exam.post(f"{API}/exams/sessions/{sid}/results/publish", json={"publish": False})
    assert students["2026BCA001"].get(f"{API}/me/results").json()["results"] == []
    assert students["2026BCA001"].get(f"{API}/me/results/{rohan['results'][0]['id']}.pdf").status_code == 404
