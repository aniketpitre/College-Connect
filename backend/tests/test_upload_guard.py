from datetime import timedelta

from tests.academics_fixtures import API, MONDAY, academics, college  # noqa: F401
from tests.test_attendance import at, ist, save
from tests.test_marks import marks, scheme  # noqa: F401


def test_upload_guard_and_export(monkeypatch, marks, client, sign_in):  # noqa: F811
    t, s, exam = marks["teachers"], marks["subjects"], marks["exam"]
    rao, hod = t["rao"]["client"], t["hod"]["client"]
    slot_id = rao.get(f"{API}/timetable/week", params={"mine": True, "day": MONDAY.isoformat()}).json()["days"][0][
        "lectures"
    ][0]["slot_id"]
    st = marks["students"]
    # Om misses 3 of 4 Monday lectures (25%); Neha misses the unit test on the first Monday.
    for week, absent in enumerate([[st["2026BCA003"], st["2026BCA002"]], [st["2026BCA003"]], [st["2026BCA003"]], []]):
        day = MONDAY + timedelta(days=7 * week)
        at(monkeypatch, ist(day, 10, 5))
        assert save(rao, slot_id, absent, day=day).status_code == 200
    components = [{"name": "Unit test 1", "max": 30, "held_on": MONDAY.isoformat()}, {"name": "Assignment", "max": 10}]
    scheme(exam, s["BCA101"], components=components, deadline="2026-09-30")
    rows = {"2026BCA001": {"c1": 25, "c2": 9}, "2026BCA002": {"c1": 12, "c2": 8}, "2026BCA003": {"c1": "AB"}}
    r = rao.put(
        f"{API}/marks/sheet",
        json={**marks["sheet"], "marks": {st[p]: m for p, m in rows.items()}, "base_version": 0},
    )
    assert r.status_code == 200, r.text

    detail = exam.get(f"{API}/marks/guard/detail", params=marks["sheet"]).json()
    assert detail["counts"] == {"missing": 1, "above_max": 0, "absent_marked": 1, "ineligible": 1}
    kinds = {(i["kind"], i["prn"]) for i in detail["issues"]}
    assert kinds == {("missing", "2026BCA003"), ("absent_marked", "2026BCA002"), ("ineligible", "2026BCA003")}
    assert not detail["ready"]
    assert exam.get(f"{API}/marks/guard/export", params=marks["sheet"]).json()["error"]["code"] == "not_ready"

    dash = exam.get(f"{API}/marks/guard").json()
    assert dash["rows"][0]["counts"]["missing"] == 1 and dash["departments"][0]["subjects"] == 1
    assert hod.get(f"{API}/marks/guard").json()["rows"][0]["code"] == "BCA101"
    assert t["comhod"]["client"].get(f"{API}/marks/guard").json()["rows"] == []
    assert t["comhod"]["client"].get(f"{API}/marks/guard/detail", params=marks["sheet"]).status_code == 403
    assert rao.get(f"{API}/marks/guard").status_code == 403

    # Fix the missing mark, export, and check the file.
    rao.put(f"{API}/marks/sheet", json={**marks["sheet"], "marks": {st["2026BCA003"]: {"c2": 4}}, "base_version": 1})
    got = exam.get(f"{API}/marks/guard/export", params=marks["sheet"])
    assert got.status_code == 200
    lines = got.content.decode().strip().splitlines()
    assert lines[0] == "PRN,Student name,Subject code,Internal marks,Maximum"
    assert sorted(lines[1:]) == sorted(
        [
            "2026BCA001,Rohan Patil,BCA101,34,40",
            "2026BCA002,Neha Joshi,BCA101,20,40",
            "2026BCA003,Om Shinde,BCA101,4,40",
        ]
    )
    assert hod.get(f"{API}/marks/guard/export", params=marks["sheet"]).status_code == 403

    check = lambda data: exam.post(  # noqa: E731
        f"{API}/marks/guard/check-file", params=marks["sheet"], files={"file": ("u.csv", data, "text/csv")}
    ).json()
    assert check(got.content) == {"ok": True, "rows": 3, "problems": []}
    broken = "\n".join([lines[0], lines[1].replace(",40", ",50"), lines[2].replace("BCA101", "BCA102")]).encode()
    result = check(broken)
    assert not result["ok"] and len(result["problems"]) == 3  # wrong maximum, wrong code, one student missing
    assert check(b"PRN;Name\n")["problems"][0].startswith("The first row must be")
