import io
import threading

from pypdf import PdfReader

from app.core import email
from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401

API = "/api/v1/fees"


def _ready(client, sign_in, fees):  # noqa: F811
    sign_in(client, ["accounts"], name="Kavita Deshmukh")
    client.post(f"{API}/structures", json=structure_body(fees))
    client.post(
        f"{API}/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    return client


def _collect(client, fees, prn="2026BCA001", amount=5_000 * RS, **extra):  # noqa: F811
    body = {
        "student_id": fees["students"][prn],
        "academic_year_id": fees["year"],
        "amount": amount,
        "mode": "cash",
        **extra,
    }
    return client.post(f"{API}/collect", json=body)


def _text(pdf_bytes: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_collect_issues_a_receipt_and_posts_the_payment(client, sign_in, fees, db):  # noqa: F811
    _ready(client, sign_in, fees)
    r = _collect(client, fees, amount=21_500 * RS)
    assert r.status_code == 201, r.text
    receipt = r.json()
    assert receipt["number"] == "R/2026-27/000001"
    # Paid in fee-structure order: tuition (20,000) first, then development.
    assert [(ln["code"], ln["amount"]) for ln in receipt["lines"]] == [("TUITION", 20_000 * RS), ("DEV", 1_500 * RS)]
    acct = client.get(f"{API}/students/{fees['students']['2026BCA001']}").json()
    assert acct["balance"] == 4_500 * RS and acct["paid"] == 21_500 * RS
    assert acct["entries"][-1]["receipt_number"] == "R/2026-27/000001"
    assert db.audit_log.find_one({"action": "fees.collected"})["details"]["receipt"] == "R/2026-27/000001"


def test_rules(client, sign_in, fees):  # noqa: F811
    _ready(client, sign_in, fees)
    too_much = _collect(client, fees, amount=30_000 * RS)
    assert too_much.status_code == 422 and too_much.json()["error"]["field"] == "amount"
    no_ref = _collect(client, fees, mode="upi")
    assert no_ref.status_code == 422 and no_ref.json()["error"]["field"] == "reference"
    no_bank = _collect(client, fees, mode="cheque", reference="004512")
    assert no_bank.status_code == 422 and no_bank.json()["error"]["field"] == "bank"
    assert _collect(client, fees, amount=0).status_code == 422
    # Failed attempts used no receipt number.
    assert _collect(client, fees, mode="upi", reference="UTR 4111 2222").json()["number"] == "R/2026-27/000001"
    _collect(client, fees, amount=21_000 * RS)
    nothing = _collect(client, fees, amount=1 * RS)
    assert nothing.status_code == 409 and nothing.json()["error"]["code"] == "nothing_due"


def test_two_cashiers_at_once_never_share_a_number(client, sign_in, fees, db):  # noqa: F811
    _ready(client, sign_in, fees)
    cashiers = []
    for _ in range(12):
        c = new_client(client)
        sign_in(c, ["accounts"])
        cashiers.append(c)
    results: list = []
    start = threading.Barrier(len(cashiers))

    def run(c, prn):
        start.wait()
        results.append(_collect(c, fees, prn=prn, amount=1_000 * RS))

    prns = list(fees["students"])
    threads = [threading.Thread(target=run, args=(c, prns[i % 3])) for i, c in enumerate(cashiers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r.status_code == 201 for r in results), [r.text for r in results if r.status_code != 201]
    numbers = sorted(r.json()["number"] for r in results)
    assert numbers == [f"R/2026-27/{i:06d}" for i in range(1, 13)]  # sequential, no gaps, no repeats
    assert db.receipts.count_documents({}) == 12
    assert db.ledger_entries.count_documents({"type": "payment"}) == 12


def test_receipt_pdf_original_then_duplicate(client, sign_in, fees):  # noqa: F811
    _ready(client, sign_in, fees)
    receipt = _collect(client, fees, amount=1_250 * RS + 50, mode="cheque", reference="004512", bank="SBI Pune").json()
    first = client.get(f"{API}/receipts/{receipt['id']}/pdf")
    assert first.status_code == 200 and first.headers["content-type"] == "application/pdf"
    text = _text(first.content)
    assert "R/2026-27/000001" in text and "ORIGINAL" in text and "Rohan Patil" in text
    assert "Rupees One Thousand Two Hundred Fifty and Fifty Paise Only" in text
    assert "Subject to realisation" in text and f"/verify/{receipt['verify_code']}" in text.replace("\n", "")
    again = _text(client.get(f"{API}/receipts/{receipt['id']}/pdf").content)
    assert "DUPLICATE" in again and "ORIGINAL" not in again


def test_today_and_receipt_list(client, sign_in, fees):  # noqa: F811
    _ready(client, sign_in, fees)
    _collect(client, fees, amount=1_000 * RS)
    _collect(client, fees, prn="2026BCA002", amount=2_000 * RS, mode="upi", reference="UPI123")
    today = client.get(f"{API}/today").json()
    assert today["total"] == 3_000 * RS and today["count"] == 2
    assert {m["mode"]: m["amount"] for m in today["by_mode"]} == {"upi": 2_000 * RS, "cash": 1_000 * RS}
    assert len(client.get(f"{API}/receipts", params={"date_from": today["date"], "date_to": today["date"]}).json()) == 2
    assert [r["number"] for r in client.get(f"{API}/receipts", params={"number": "2"}).json()] == ["R/2026-27/000002"]


def test_email_receipt(client, sign_in, fees, db):  # noqa: F811
    _ready(client, sign_in, fees)
    receipt = _collect(client, fees).json()
    assert client.post(f"{API}/receipts/{receipt['id']}/email").status_code == 409  # no email on record
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"email": "rohan@example.in"}})
    email.OUTBOX.clear()
    r = client.post(f"{API}/receipts/{receipt['id']}/email")
    assert r.status_code == 200 and r.json()["sent_to"] == "rohan@example.in"
    assert "R/2026-27/000001" in email.OUTBOX[-1].text and "/verify/" in email.OUTBOX[-1].text


def test_who_can_collect(client, sign_in, fees):  # noqa: F811
    _ready(client, sign_in, fees)
    for role in ("office", "principal"):
        other = new_client(client)
        sign_in(other, [role])
        assert _collect(other, fees).status_code == 403
        assert other.get(f"{API}/today").status_code == 200  # but can see collections
