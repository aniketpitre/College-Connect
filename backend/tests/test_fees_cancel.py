import io

from pypdf import PdfReader

from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401

API = "/api/v1/fees"


def _setup(client, sign_in, fees):  # noqa: F811
    sign_in(client, ["accounts"])
    client.post(f"{API}/structures", json=structure_body(fees))
    client.post(
        f"{API}/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    principal = new_client(client)
    sign_in(principal, ["principal"])
    return principal


def _pay(client, fees, amount, prn="2026BCA001"):  # noqa: F811
    body = {"student_id": fees["students"][prn], "academic_year_id": fees["year"], "amount": amount, "mode": "cash"}
    return client.post(f"{API}/collect", json=body).json()


def test_cancellation_needs_approval_and_reverses_the_payment(client, sign_in, fees, db):  # noqa: F811
    principal = _setup(client, sign_in, fees)
    sid = fees["students"]["2026BCA001"]
    receipt = _pay(client, fees, 10_000 * RS)
    req = client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Wrong student selected"})
    assert req.status_code == 201
    dup = client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Asking again"})
    assert dup.status_code == 409  # one open request per receipt
    assert client.get(f"{API}/students/{sid}").json()["balance"] == 16_000 * RS  # unchanged until approved

    ok = principal.post(f"/api/v1/approvals/{req.json()['id']}/decide", json={"approve": True})
    assert ok.status_code == 200
    acct = client.get(f"{API}/students/{sid}").json()
    assert acct["balance"] == 26_000 * RS
    payment, reversal = acct["entries"][-2], acct["entries"][-1]
    assert payment["reversed"] is True and reversal["type"] == "reversal" and reversal["reverses"] == payment["id"]
    r = client.get(f"{API}/receipts/{receipt['id']}").json()
    assert r["status"] == "cancelled" and r["cancel_reason"] == "Wrong student selected"
    pdf = client.get(f"{API}/receipts/{receipt['id']}/pdf").content
    assert "CANCELLED" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert (
        client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Once more"}).status_code == 409
    )
    # The number is never reused: the next receipt is 000002.
    assert _pay(client, fees, 1_000 * RS)["number"] == "R/2026-27/000002"
    assert client.get(f"{API}/today").json()["cancelled"] == 1


def test_rejected_cancellation_changes_nothing(client, sign_in, fees):  # noqa: F811
    principal = _setup(client, sign_in, fees)
    receipt = _pay(client, fees, 10_000 * RS)
    req = client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Typing mistake"}).json()
    principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": False, "reason": "Receipt is correct"})
    assert client.get(f"{API}/receipts/{receipt['id']}").json()["status"] == "valid"
    # A new request can be made after a rejection.
    assert (
        client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Checked again"}).status_code
        == 201
    )


def test_refund_of_a_credit(client, sign_in, fees, db):  # noqa: F811
    principal = _setup(client, sign_in, fees)
    sid = fees["students"]["2026BCA001"]
    _pay(client, fees, 26_000 * RS)
    no_credit = client.post(
        f"{API}/refunds",
        json={"student_id": sid, "academic_year_id": fees["year"], "amount": 100, "mode": "cash", "reason": "Overpaid"},
    )
    assert no_credit.status_code == 409
    # The scholarship is sanctioned after the student paid in full: they are now in credit.
    s = client.post(
        f"{API}/scholarships",
        json={"student_id": sid, "academic_year_id": fees["year"], "scheme": "NSP", "expected": 3_000 * RS},
    ).json()
    assert client.post(f"{API}/scholarships/{s['id']}/actions", json={"action": "sanction"}).status_code == 200
    too_much = client.post(
        f"{API}/refunds",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "amount": 4_000 * RS,
            "mode": "cash",
            "reason": "Scholarship credit",
        },
    )
    assert too_much.status_code == 422
    no_ref = client.post(
        f"{API}/refunds",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "amount": 3_000 * RS,
            "mode": "bank_transfer",
            "reason": "Scholarship credit",
        },
    )
    assert no_ref.status_code == 422
    req = client.post(
        f"{API}/refunds",
        json={
            "student_id": sid,
            "academic_year_id": fees["year"],
            "amount": 3_000 * RS,
            "mode": "bank_transfer",
            "reference": "NEFT 77881",
            "reason": "Scholarship credit",
        },
    ).json()
    assert client.get(f"{API}/students/{sid}").json()["balance"] == -3_000 * RS
    principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True})
    acct = client.get(f"{API}/students/{sid}").json()
    assert acct["balance"] == 0 and acct["entries"][-1]["type"] == "refund"
    assert "NEFT 77881" in acct["entries"][-1]["reason"]


def test_verify_page(client, sign_in, fees):  # noqa: F811
    principal = _setup(client, sign_in, fees)
    receipt = _pay(client, fees, 2_500 * RS)
    public = new_client(client)
    public.cookies.clear()
    r = public.get(f"/api/v1/verify/{receipt['verify_code'].lower()}")
    assert r.status_code == 200
    v = r.json()
    assert v["valid"] is True and v["number"] == "R/2026-27/000001" and v["amount"] == 2_500 * RS
    assert v["student_name"] == "Rohan P." and v["prn"] == "2026BCA***"  # just enough to match, not the full record
    assert public.get("/api/v1/verify/NOTAREALCODE").status_code == 404

    req = client.post(f"{API}/receipts/{receipt['id']}/cancel-request", json={"reason": "Duplicate entry"}).json()
    principal.post(f"/api/v1/approvals/{req['id']}/decide", json={"approve": True})
    v = public.get(f"/api/v1/verify/{receipt['verify_code']}").json()
    assert v["valid"] is False and v["status"] == "cancelled" and v["cancelled_at"]


def test_verify_is_rate_limited(client, fees):  # noqa: F811
    codes = [client.get("/api/v1/verify/NOPE").status_code for _ in range(61)]
    assert codes[-1] == 429 and set(codes[:60]) == {404}
