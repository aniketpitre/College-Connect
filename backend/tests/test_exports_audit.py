import csv
import io
from datetime import UTC, datetime, timedelta

from tests.fees_fixtures import RS, college, fees, new_client  # noqa: F401
from tests.test_portal import _charged_and_paid
from tests.test_students import sign_in_as_student

API = "/api/v1"


def _rows(content: bytes) -> list[list[str]]:
    assert content.startswith("﻿".encode())
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_export_needs_the_principals_approval(client, sign_in, fees, db):  # noqa: F811
    _charged_and_paid(client, sign_in, fees)
    db.students.update_one({"prn": "2026BCA001"}, {"$set": {"name": "=HYPERLINK(1)"}})
    admin = new_client(client)
    sign_in(admin, ["system_admin"])
    principal = new_client(client)
    sign_in(principal, ["principal"])

    # Only the System Admin asks; nobody else can.
    assert client.post(f"{API}/export/requests", json={"dataset": "students", "reason": "Backup"}).status_code == 403
    assert principal.post(f"{API}/export/requests", json={"dataset": "fees", "reason": "Backup"}).status_code == 403
    r = admin.post(f"{API}/export/requests", json={"dataset": "students", "reason": "Yearly backup"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    rid = r.json()["id"]
    dup = admin.post(f"{API}/export/requests", json={"dataset": "students", "reason": "Yearly backup"})
    assert dup.status_code == 409
    assert admin.post(f"{API}/export/requests", json={"dataset": "x", "reason": "Yearly"}).status_code == 422

    # Not downloadable until approved; the requester can't approve their own.
    assert admin.get(f"{API}/export/requests/{rid}/download").json()["error"]["code"] == "not_approved"
    assert admin.post(f"{API}/export/requests/{rid}/decide", json={"approve": True}).status_code == 403
    assert principal.post(f"{API}/export/requests/{rid}/decide", json={"approve": False}).status_code == 422
    listed = principal.get(f"{API}/export/requests").json()
    assert [x["id"] for x in listed["requests"]] == [rid] and "fees" in listed["datasets"]
    assert client.get(f"{API}/export/requests").status_code == 403  # accounts staff

    decided = principal.post(f"{API}/export/requests/{rid}/decide", json={"approve": True})
    assert decided.status_code == 200 and decided.json()["downloadable"] is True
    assert principal.post(f"{API}/export/requests/{rid}/decide", json={"approve": True}).status_code == 409
    # Only the requester downloads.
    assert principal.get(f"{API}/export/requests/{rid}/download").status_code == 403

    got = admin.get(f"{API}/export/requests/{rid}/download")
    assert got.status_code == 200 and got.headers["content-type"].startswith("text/csv")
    rows = _rows(got.content)
    assert rows[0][:2] == ["PRN", "Name"] and len(rows) == 1 + db.students.count_documents({})
    by_prn = {row[0]: row for row in rows[1:]}
    assert by_prn["2026BCA001"][1] == "'=HYPERLINK(1)"  # spreadsheet formulas are defused
    assert by_prn["2026BCA002"][1] == "Neha Joshi"
    assert db.audit_log.count_documents({"action": "exports.downloaded"}) == 1

    # The link expires after 24 hours.
    db.export_requests.update_one(
        {"dataset": "students"}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(minutes=1)}}
    )
    assert admin.get(f"{API}/export/requests/{rid}/download").status_code == 410


def test_fee_and_receipt_exports(client, sign_in, fees, db):  # noqa: F811
    receipts = _charged_and_paid(client, sign_in, fees)
    admin = new_client(client)
    sign_in(admin, ["system_admin"])
    principal = new_client(client)
    sign_in(principal, ["principal"])
    out = {}
    for dataset in ("fees", "receipts"):
        rid = admin.post(f"{API}/export/requests", json={"dataset": dataset, "reason": "Audit by CA"}).json()["id"]
        principal.post(f"{API}/export/requests/{rid}/decide", json={"approve": True})
        out[dataset] = _rows(admin.get(f"{API}/export/requests/{rid}/download").content)

    header, *rows = out["fees"]
    by_prn = {r[0]: dict(zip(header, r, strict=True)) for r in rows}
    assert by_prn["2026BCA001"]["Fee for the year"] == "26000.00"
    assert by_prn["2026BCA001"]["Payment"] == "10000.00"
    assert by_prn["2026BCA001"]["Balance"] == "16000.00"
    assert by_prn["2026BCA002"]["Balance"] == "22000.00"

    header, *rows = out["receipts"]
    numbers = {r[0] for r in rows}
    assert numbers == {receipts["2026BCA001"]["number"], receipts["2026BCA002"]["number"]}
    assert dict(zip(header, rows[0], strict=True))["Amount"] in {"10000.00", "4000.00"}
    _ = RS


def test_student_downloads_only_their_own_data(client, sign_in, fees, db):  # noqa: F811
    receipts = _charged_and_paid(client, sign_in, fees)
    student = new_client(client)
    sign_in_as_student(student, db, "2026BCA001")
    r = student.get(f"{API}/me/data-export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["student_record"]["prn"] == "2026BCA001"
    assert [x["number"] for x in data["receipts"]] == [receipts["2026BCA001"]["number"]]
    assert {e["type"] for e in data["fee_ledger"]} == {"Fee for the year", "Payment"}
    assert "password_hash" not in r.text and "2026BCA002" not in r.text
    assert client.get(f"{API}/me/data-export").status_code == 403  # staff have no student record


def test_audit_viewer(client, sign_in, fees, db):  # noqa: F811
    _charged_and_paid(client, sign_in, fees)
    admin = new_client(client)
    sign_in(admin, ["system_admin"], name="Asha Admin")
    admin.post(f"{API}/export/requests", json={"dataset": "fees", "reason": "Backup copy"})
    assert client.get(f"{API}/audit").status_code == 403  # accounts can't read the audit log

    principal = new_client(client)
    sign_in(principal, ["principal"])
    page = principal.get(f"{API}/audit").json()
    assert page["rows"] and page["rows"][0]["action"] == "exports.requested"
    assert page["rows"][0]["actor"] == "Asha Admin"
    times = [r["at"] for r in page["rows"]]
    assert times == sorted(times, reverse=True)

    fees_only = principal.get(f"{API}/audit", params={"area": "fees"}).json()["rows"]
    assert fees_only and all(r["action"].startswith("fees.") for r in fees_only)
    paid = [r for r in fees_only if r["target_type"] == "student"]
    assert any(r["target"] and "(2026BCA" in r["target"] for r in paid)
    by_actor = principal.get(f"{API}/audit", params={"actor": "asha"}).json()["rows"]
    assert {r["actor"] for r in by_actor} == {"Asha Admin"}
    assert principal.get(f"{API}/audit", params={"area": "nope"}).status_code == 422
    assert principal.get(f"{API}/audit", params={"from": "04-10-2026"}).status_code == 422
    future = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    assert principal.get(f"{API}/audit", params={"from": future}).json()["rows"] == []

    # Paging: 100 per page, then the rest.
    db.audit_log.insert_many(
        [{"at": datetime.now(UTC) - timedelta(days=30, seconds=i), "action": "auth.logout"} for i in range(120)]
    )
    first = principal.get(f"{API}/audit").json()
    assert len(first["rows"]) == 100 and first["next_before"]
    second = principal.get(f"{API}/audit", params={"before": first["next_before"]}).json()
    assert second["rows"] and second["rows"][0]["at"] < first["rows"][-1]["at"]
    ids = {r["id"] for r in first["rows"]} & {r["id"] for r in second["rows"]}
    assert not ids
