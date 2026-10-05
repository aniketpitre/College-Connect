from dataclasses import replace
from datetime import timedelta

from app.core import email
from app.core.config import settings
from app.modules.attendance import router as attendance_router
from app.modules.attendance.stats import can_miss, must_attend
from tests.academics_fixtures import API, MONDAY, academics, college  # noqa: F401
from tests.fees_fixtures import new_client
from tests.test_attendance import at, ist, save, week  # noqa: F401
from tests.test_students import sign_in_as_student


def test_can_miss_and_must_attend():
    assert can_miss(20, 18, 75) == 4  # 18/24 = 75%
    assert must_attend(20, 18, 75) == 0
    assert can_miss(20, 12, 75) == 0
    assert must_attend(20, 12, 75) == 12  # 24/32 = 75%
    assert must_attend(4, 2, 75) == 4 and can_miss(4, 3, 75) == 0
    assert can_miss(0, 0, 75) == 0 and must_attend(0, 0, 75) == 0


def _mondays(monkeypatch, week, absent_by_week):  # noqa: F811
    """Marks the Monday C lecture for consecutive weeks; absent_by_week[i] = PRNs absent in week i."""
    rao = week["teachers"]["rao"]["client"]
    for i, prns in enumerate(absent_by_week):
        day = MONDAY + timedelta(days=7 * i)
        at(monkeypatch, ist(day, 10, 5))
        r = save(rao, week["c"], [week["students"][p] for p in prns], day=day)
        assert r.status_code == 200, r.text


def test_student_sees_percent_and_what_to_do(monkeypatch, week, client, db):  # noqa: F811
    # Rohan misses 3 of 8; Neha misses 1 (but one is exempted); Om never misses.
    plan = [["2026BCA001", "2026BCA002"], ["2026BCA001"], ["2026BCA001"], [], [], [], [], []]
    _mondays(monkeypatch, week, plan)
    week["office"].post(
        f"{API}/attendance/exemptions",
        json={"student_id": week["students"]["2026BCA002"], "kind": "official_duty", "from_date": MONDAY.isoformat(),
              "to_date": MONDAY.isoformat(), "reason": "University sports meet"},
    )  # fmt: skip
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    me = student.get(f"{API}/me/attendance").json()
    c = me["subjects"][0]
    assert (c["code"], c["held"], c["attended"], c["percent"]) == ("BCA101", 8, 5, 62.5)
    assert c["status"] == "critical" and c["must_attend"] == 4 and c["can_miss"] == 0
    assert me["minimum"] == 75 and me["overall"]["percent"] == 62.5
    assert [x["mark"] for x in me["days"][-1]["lectures"]] == ["absent"]  # oldest day last
    home = student.get(f"{API}/me/home").json()
    assert home["cards"][0]["kind"] == "attendance_low" and home["cards"][0]["must_attend"] == 4

    neha = new_client(client)
    sign_in_as_student(neha, db, "2026BCA002")
    n = neha.get(f"{API}/me/attendance").json()["subjects"][0]
    assert n["attended"] == 8 and n["percent"] == 100.0 and n["can_miss"] == 2
    assert neha.get(f"{API}/me/attendance").json()["days"][-1]["lectures"][0]["mark"] == "exempt"


def test_class_report_and_defaulters(monkeypatch, week, client, sign_in):  # noqa: F811
    _mondays(monkeypatch, week, [["2026BCA001"], ["2026BCA001"], [], []])
    t = week["teachers"]
    report = t["hod"]["client"].get(f"{API}/attendance/report", params={"division_id": week["div"][1]})
    assert report.status_code == 200
    body = report.json()
    assert body["class"] == "BCA FY A" and [s["code"] for s in body["subjects"]] == ["BCA101"]
    assert body["subjects"][0]["held"] == 4
    rows = {r["prn"]: r for r in body["students"]}
    assert rows["2026BCA001"]["overall"] == 50.0 and rows["2026BCA001"]["defaulter"]
    assert rows["2026BCA003"]["status"] == "ok" and not rows["2026BCA003"]["defaulter"]
    # Date range.
    early = (
        t["hod"]["client"]
        .get(
            f"{API}/attendance/report",
            params={"division_id": week["div"][1], "date_from": (MONDAY + timedelta(days=14)).isoformat()},
        )
        .json()
    )
    assert early["subjects"][0]["held"] == 2

    # Who may see it: teachers of the class, HOD of the department, office/principal; not others.
    assert t["rao"]["client"].get(f"{API}/attendance/report", params={"division_id": week["div"][1]}).status_code == 200
    assert (
        t["comhod"]["client"].get(f"{API}/attendance/report", params={"division_id": week["div"][1]}).status_code == 403
    )
    assert t["comhod"]["client"].get(f"{API}/attendance/classes").json() == [
        {"id": week["bcom_div"], "label": "BCOM FY A"}
    ]
    assert week["office"].get(f"{API}/attendance/report", params={"division_id": week["div"][1]}).status_code == 200
    sign_in(client, ["accounts"])
    assert client.get(f"{API}/attendance/report", params={"division_id": week["div"][1]}).status_code == 403


def test_daily_alerts_email_once_per_level(monkeypatch, week, db):  # noqa: F811
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"email": "rohan@example.com"}})
    _mondays(monkeypatch, week, [["2026BCA001"], ["2026BCA001"], [], [], [], [], []])  # 5/7 = 71.4%
    monkeypatch.setattr(attendance_router, "settings", replace(settings, cron_secret="s3cret"))
    c = week["office"]
    assert c.get(f"{API}/cron/attendance-alerts").status_code == 401
    assert c.get(f"{API}/cron/attendance-alerts", headers={"Authorization": "Bearer nope"}).status_code == 401
    email.OUTBOX.clear()
    r = c.get(f"{API}/cron/attendance-alerts", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and r.json()["sent"] == 1
    mail = email.OUTBOX[-1]
    assert mail.to == "rohan@example.com" and "71.4%" in mail.text and "next" in mail.text
    # Not again for the same level.
    assert c.get(f"{API}/cron/attendance-alerts", headers={"Authorization": "Bearer s3cret"}).json()["sent"] == 0
    assert db.attendance_alerts.count_documents({}) == 1
