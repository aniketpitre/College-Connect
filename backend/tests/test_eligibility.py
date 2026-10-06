from datetime import UTC, datetime

from bson import ObjectId

from tests.fees_fixtures import college, fees, new_client  # noqa: F401
from tests.test_students import sign_in_as_student

API = "/api/v1"


def _by_code(data):
    return {s["code"]: s for s in data["schemes"]}


def test_student_sees_schemes_with_reasons_and_missing_documents(client, sign_in, db, fees):  # noqa: F811
    neha_id = ObjectId(fees["students"]["2026BCA002"])  # OBC
    db.students.update_one(
        {"_id": neha_id},
        {
            "$set": {
                "address": {"state": "Maharashtra"},
                "previous_education": {"exam": "HSC", "percentage": 85.0},
                "gender": "female",
            }
        },
    )
    neha, rohan, accounts = new_client(client), new_client(client), new_client(client)
    sign_in_as_student(neha, db, "2026BCA002")
    sign_in_as_student(rohan, db, "2026BCA001")
    sign_in(accounts, ["accounts"])

    # Without her family income the OBC scheme can't be judged yet; the SC one isn't for her.
    s = _by_code(neha.get(f"{API}/me/scholarship-check").json())
    assert s["postmatric-obc"]["status"] == "check" and s["postmatric-obc"]["unknown"] == ["income"]
    assert s["postmatric-sc"]["status"] == "not_eligible"
    assert s["postmatric-sc"]["failed"] == [{"rule": "category", "allowed": ["SC"]}]

    # She declares ₹1.2 lakh: eligible on the rules; the documents she still has to upload are listed.
    s = _by_code(neha.put(f"{API}/me/scholarship-check/income", json={"family_income": 120_000}).json())
    assert s["postmatric-obc"]["status"] == "missing_documents"
    assert s["postmatric-obc"]["missing_documents"] == [
        "caste_certificate", "income_certificate", "domicile_certificate", "hsc_marksheet", "aadhaar_masked"
    ]  # fmt: skip
    assert s["central-sector"]["status"] == "missing_documents"  # 85% in HSC, first year
    docs = [
        {"id": ObjectId(), "type": t, "status": "pending", "file_id": ObjectId(), "filename": f"{t}.pdf",
         "uploaded_at": datetime.now(UTC)}
        for t in ("caste_certificate", "income_certificate", "domicile_certificate", "hsc_marksheet", "aadhaar_masked")
    ]  # fmt: skip
    db.students.update_one({"_id": neha_id}, {"$set": {"documents": docs}})
    data = neha.get(f"{API}/me/scholarship-check").json()
    assert data["schemes"][0]["status"] == "likely" and _by_code(data)["postmatric-obc"]["status"] == "likely"

    # Once Accounts records her application, the scheme shows as applied.
    obc = "Post-Matric Scholarship for OBC students"
    db.scholarships.insert_one(
        {"student_id": neha_id, "academic_year_id": ObjectId(fees["year"]), "scheme": obc,
         "status": "expected", "expected": 0, "sanctioned": 0, "received": 0}
    )  # fmt: skip
    s = _by_code(neha.get(f"{API}/me/scholarship-check").json())
    assert (s["postmatric-obc"]["status"], s["postmatric-obc"]["application_status"]) == ("applied", "expected")

    # Rohan (open category) is told what is missing for the EBC scheme, not someone else's details.
    r = _by_code(rohan.get(f"{API}/me/scholarship-check").json())
    assert r["ebc-shahu-maharaj"]["status"] == "check" and set(r["ebc-shahu-maharaj"]["unknown"]) == {
        "income",
        "domicile",
    }
    assert r["postmatric-obc"]["status"] == "not_eligible"

    # Accounts: candidates for a scheme who haven't applied; scheme rules are editable.
    cands = accounts.get(f"{API}/scholarship-schemes/central-sector/candidates").json()["students"]
    assert [(c["prn"], c["status"]) for c in cands] == [
        ("2026BCA002", "likely"),  # she applied for the OBC scheme, not this one
        ("2026BCA001", "check"),  # HSC percentage not recorded
        ("2026BCA003", "check"),
    ]
    scheme = next(x for x in accounts.get(f"{API}/scholarship-schemes").json() if x["code"] == "ebc-shahu-maharaj")
    scheme["income_limit"] = 900_000
    assert accounts.put(f"{API}/scholarship-schemes/ebc-shahu-maharaj", json=scheme).json()["income_limit"] == 900_000
    assert rohan.get(f"{API}/scholarship-schemes").status_code == 403
    assert rohan.put(f"{API}/scholarship-schemes/ebc-shahu-maharaj", json=scheme).status_code == 403
