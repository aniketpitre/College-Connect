import io
from datetime import date, timedelta

from pypdf import PdfReader

from tests.fees_fixtures import RS, college, fees, new_client, structure_body  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"


def _charged_and_paid(client, sign_in, fees, due_first=None):  # noqa: F811
    sign_in(client, ["accounts"])
    client.post(f"{API}/fees/structures", json=structure_body(fees, due_first=due_first))
    client.post(
        f"{API}/fees/demands/generate",
        json={"academic_year_id": fees["year"], "programme_id": fees["bca"], "year_of_study": 1, "dry_run": False},
    )
    receipts = {}
    for prn, amount in (("2026BCA001", 10_000 * RS), ("2026BCA002", 4_000 * RS)):
        r = client.post(
            f"{API}/fees/collect",
            json={
                "student_id": fees["students"][prn],
                "academic_year_id": fees["year"],
                "amount": amount,
                "mode": "cash",
            },
        )
        receipts[prn] = r.json()
    return receipts


def test_student_sees_their_fees_and_receipts(client, sign_in, fees, db):  # noqa: F811
    receipts = _charged_and_paid(client, sign_in, fees)
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    mine = student.get(f"{API}/me/fees").json()
    assert mine["balance"] == 16_000 * RS and mine["paid"] == 10_000 * RS
    assert [r["number"] for r in mine["receipts"]] == [receipts["2026BCA001"]["number"]]
    assert len(mine["installments"]) == 2 and mine["years"][0]["name"] == "2026-27"
    assert "verify_code" not in mine["receipts"][0]

    pdf = student.get(f"{API}/me/receipts/{receipts['2026BCA001']['id']}/pdf")
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert pdf.status_code == 200 and "STUDENT COPY" in text
    # The office's first print is still the ORIGINAL.
    office_pdf = client.get(f"{API}/fees/receipts/{receipts['2026BCA001']['id']}/pdf").content
    assert "ORIGINAL" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(office_pdf)).pages)

    statement = student.get(f"{API}/me/fees/statement.pdf")
    st_text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(statement.content)).pages)
    assert "Fee statement 2026-27" in st_text and "Rs. 16,000.00" in st_text and "2026BCA001" in st_text


def test_student_cannot_reach_another_students_fees(client, sign_in, fees, db):  # noqa: F811
    receipts = _charged_and_paid(client, sign_in, fees)
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    assert student.get(f"{API}/me/receipts/{receipts['2026BCA002']['id']}/pdf").status_code == 404
    assert student.get(f"{API}/fees/students/{fees['students']['2026BCA002']}").status_code == 403
    assert student.get(f"{API}/fees/receipts/{receipts['2026BCA002']['id']}/pdf").status_code == 403
    assert student.get(f"{API}/me/fees", params={"academic_year_id": "64b7f0000000000000000000"}).status_code == 404
    # Staff have no student record: the student routes refuse them.
    assert client.get(f"{API}/me/fees").status_code == 403


def test_home_cards(client, sign_in, fees, db):  # noqa: F811
    _charged_and_paid(client, sign_in, fees, due_first=date.today() - timedelta(days=3))
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA002")
    home = student.get(f"{API}/me/home").json()
    assert home["name"] == "Neha Joshi" and home["class"].startswith("BCA")
    assert home["balance"] == 22_000 * RS
    assert home["cards"][0]["kind"] == "fee_overdue" and home["cards"][0]["amount"] == 9_000 * RS

    other = new_client(client)
    sign_in_as_student(other, db, "2026BCA003")
    db.students.update_one(
        {"prn": "2026BCA003"},
        {"$push": {"documents": {"id": "x", "type": "hsc_marksheet", "status": "rejected", "reason": "Blurred"}}},
    )
    kinds = [c["kind"] for c in other.get(f"{API}/me/home").json()["cards"]]
    assert kinds == ["fee_overdue", "document_rejected"]


def test_due_soon_card(client, sign_in, fees, db):  # noqa: F811
    _charged_and_paid(client, sign_in, fees, due_first=date.today() + timedelta(days=5))
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA003")
    card = student.get(f"{API}/me/home").json()["cards"][0]
    assert card["kind"] == "fee_due_soon" and card["amount"] == 13_000 * RS
