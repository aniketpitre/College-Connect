from datetime import date, timedelta

from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401

API = "/api/v1/fees"


def _accounts(client, sign_in):
    sign_in(client, ["accounts"])
    return client


def test_structures_validate_totals_and_are_unique(client, sign_in, fees):  # noqa: F811
    _accounts(client, sign_in)
    body = structure_body(fees)
    bad = {**body, "installments": [{**body["installments"][0], "amount": 100}]}
    r = client.post(f"{API}/structures", json=bad)
    assert r.status_code == 422 and r.json()["error"]["field"] == "installments"
    r = client.post(f"{API}/structures", json=body)
    assert r.status_code == 201 and r.json()["total"] == 26_000 * RS
    assert client.post(f"{API}/structures", json=body).status_code == 409
    assert client.post(f"{API}/structures", json={**body, "category_id": fees["obc"]}).status_code == 201
    assert len(client.get(f"{API}/structures", params={"academic_year_id": fees["year"]}).json()) == 2


def test_demands_use_the_category_structure_and_lock_it(client, sign_in, fees, db):  # noqa: F811
    _accounts(client, sign_in)
    default = client.post(f"{API}/structures", json=structure_body(fees)).json()
    client.post(f"{API}/structures", json=structure_body(fees, category=fees["obc"], tuition=10_000))
    req = {"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1}

    preview = client.post(f"{API}/demands/generate", json={**req, "dry_run": True}).json()
    assert preview["counts"] == {"charge": 3, "already_charged": 0, "no_structure": 0}
    assert preview["total"] == (26_000 * 2 + 16_000) * RS
    assert db.ledger_entries.count_documents({}) == 0

    client.post(f"{API}/demands/generate", json={**req, "dry_run": False})
    again = client.post(f"{API}/demands/generate", json={**req, "dry_run": False}).json()
    assert again["counts"]["already_charged"] == 3  # never charged twice

    neha = client.get(f"{API}/students/{fees['students']['2026BCA002']}").json()
    assert neha["balance"] == 16_000 * RS and neha["demand"] == 16_000 * RS
    assert [h["code"] for h in neha["by_head"]] == ["TUITION", "DEV", "EXAM"]
    assert len(neha["installments"]) == 2 and neha["overdue"] == 0

    locked = client.put(
        f"{API}/structures/{default['id']}",
        json={k: v for k, v in structure_body(fees).items() if k in ("name", "items", "installments", "late_fee")},
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "locked"


def _charged(client, sign_in, fees, **kw):  # noqa: F811
    _accounts(client, sign_in)
    client.post(f"{API}/structures", json=structure_body(fees, **kw))
    client.post(
        f"{API}/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    return fees["students"]["2026BCA001"]


def test_concession_needs_the_principal_and_not_the_requester(client, sign_in, fees, db):  # noqa: F811
    sid = _charged(client, sign_in, fees)
    too_much = client.post(
        f"{API}/concessions",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "head_id": fees["heads"]["EXAM"],
            "amount": 5_000 * RS,
            "kind": "merit",
            "reason": "First in class",
        },
    )
    assert too_much.status_code == 422 and too_much.json()["error"]["field"] == "amount"
    req = client.post(
        f"{API}/concessions",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "head_id": fees["heads"]["TUITION"],
            "amount": 5_000 * RS,
            "kind": "staff_ward",
            "reason": "Child of a teacher",
        },
    ).json()
    assert req["status"] == "pending"
    assert client.get(f"{API}/students/{sid}").json()["balance"] == 26_000 * RS  # nothing changes until approved
    assert (
        client.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True}).status_code == 403
    )  # accounts can't approve

    principal = new_client(client)
    sign_in(principal, ["principal"])
    inbox = principal.get("/api/v1/approvals").json()
    assert inbox[0]["student_name"] == "Rohan Patil" and inbox[0]["details"]["head"] == "TUITION"
    assert principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": False}).status_code == 422
    ok = principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True, "reason": "As per policy"})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    account = client.get(f"{API}/students/{sid}").json()
    assert account["balance"] == 21_000 * RS and account["concessions"] == 5_000 * RS
    assert principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True}).status_code == 409


def test_nobody_approves_their_own_request(client, sign_in, fees, db):  # noqa: F811
    sid = _charged(client, sign_in, fees)
    both = new_client(client)
    sign_in(both, ["accounts", "principal"])
    req = both.post(
        f"{API}/concessions",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "head_id": fees["heads"]["DEV"],
            "amount": 1_000 * RS,
            "kind": "sibling",
            "reason": "Brother studies here",
        },
    ).json()
    r = both.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True})
    assert r.status_code == 403 and r.json()["error"]["code"] == "same_person"


def test_scholarship_lifecycle(client, sign_in, fees):  # noqa: F811
    sid = _charged(client, sign_in, fees)
    s = client.post(
        f"{API}/scholarships",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "scheme": "MahaDBT Post-Matric",
            "expected": 12_000 * RS,
        },
    ).json()
    assert s["status"] == "expected"
    assert client.post(f"{API}/scholarships/{s['id']}/actions", json={"action": "receive"}).status_code == 409
    sanctioned = client.post(
        f"{API}/scholarships/{s['id']}/actions", json={"action": "sanction", "amount": 10_000 * RS}
    ).json()
    assert sanctioned["status"] == "sanctioned"
    acct = client.get(f"{API}/students/{sid}").json()
    assert acct["balance"] == 16_000 * RS and acct["scholarships"] == 10_000 * RS
    part = client.post(f"{API}/scholarships/{s['id']}/actions", json={"action": "receive", "amount": 4_000 * RS}).json()
    assert part["received"] == 4_000 * RS and part["status"] == "sanctioned"
    full = client.post(f"{API}/scholarships/{s['id']}/actions", json={"action": "receive"}).json()
    assert full["status"] == "received" and full["received"] == 10_000 * RS

    other = client.post(
        f"{API}/scholarships",
        json={"student_id": sid, "academic_year_id": fees["year"], "scheme": "NSP", "expected": 2_000 * RS},
    ).json()
    client.post(f"{API}/scholarships/{other['id']}/actions", json={"action": "sanction"})
    assert client.get(f"{API}/students/{sid}").json()["balance"] == 14_000 * RS
    rejected = client.post(
        f"{API}/scholarships/{other['id']}/actions", json={"action": "reject", "reason": "Income certificate expired"}
    ).json()
    assert rejected["status"] == "rejected"
    assert client.get(f"{API}/students/{sid}").json()["balance"] == 16_000 * RS  # reversed


def test_charges_and_late_fees(client, sign_in, fees):  # noqa: F811
    sid = _charged(client, sign_in, fees, due_first=date.today() - timedelta(days=5))
    acct = client.get(f"{API}/students/{sid}").json()
    assert acct["overdue"] == 13_000 * RS and acct["installments"][0]["overdue"] is True
    after = client.post(f"{API}/students/{sid}/late-fees", params={"academic_year_id": fees["year"]}).json()
    assert after["balance"] == 26_100 * RS
    assert (
        client.post(f"{API}/students/{sid}/late-fees", params={"academic_year_id": fees["year"]}).status_code == 409
    )  # once
    charged = client.post(
        f"{API}/students/{sid}/charges",
        json={
            "academic_year_id": fees["year"],
            "head_id": fees["heads"]["EXAM"],
            "amount": 200 * RS,
            "reason": "Duplicate ID card",
        },
    ).json()
    assert charged["balance"] == 26_300 * RS
    assert charged["entries"][-1]["reason"] == "Duplicate ID card"


def test_who_can_do_what(client, sign_in, fees):  # noqa: F811
    office = new_client(client)
    sign_in(office, ["office"])
    assert office.get(f"{API}/students/{fees['students']['2026BCA001']}").status_code == 200  # reads
    assert office.post(f"{API}/structures", json=structure_body(fees)).status_code == 403
    faculty = new_client(client)
    sign_in(faculty, ["faculty"])
    assert faculty.get(f"{API}/heads").status_code == 403
    student = new_client(client)
    sign_in(student, ["student"], kind="student", prn="2026BCA099")
    assert student.get(f"{API}/students/{fees['students']['2026BCA001']}").status_code == 403
