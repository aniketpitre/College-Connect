import io
import json
import zipfile
from urllib.parse import quote

from tests.fees_fixtures import college, fees, new_client  # noqa: F401

API = "/api/v1"
RESTORE_DB = "collegeconnect_test_restore"


def _browser_zip(c, rid):
    """What the Data export page does: the manifest, then every collection page by page."""
    manifest = c.get(f"{API}/export/requests/{rid}/full").json()
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as out:
        out.writestr("manifest.json", json.dumps({"collections": manifest["collections"]}))
        out.writestr("data-dictionary.md", manifest["dictionary_md"])
        for entry in manifest["collections"]:
            name, after, chunks, pages = entry["collection"], None, [], 0
            while True:
                url = f"{API}/export/requests/{rid}/full/{name}" + (f"?after={quote(after)}" if after else "")
                r = c.get(url)
                assert r.status_code == 200, (name, r.text)
                chunks.append(r.text)
                pages += 1
                after = r.headers.get("X-Next-After")
                if not after:
                    break
            out.writestr(f"collections/{name}.jsonl", "".join(chunks))
            entry["pages"] = pages
    return z.getvalue(), manifest


def test_full_export_restores_into_a_fresh_database(monkeypatch, client, sign_in, db, fees):  # noqa: F811
    from app.modules.exports import full
    from scripts.restore_export import check, ledger_total, restore

    monkeypatch.setattr(full, "PAGE_DOCS", 2)  # force paging even on a small database
    admin, principal, office = new_client(client), new_client(client), new_client(client)
    sign_in(admin, ["system_admin"])
    sign_in(principal, ["principal"])
    sign_in(office, ["office"])
    rid = admin.post(f"{API}/export/requests", json={"dataset": "full", "reason": "Yearly backup"}).json()["id"]
    assert admin.get(f"{API}/export/requests/{rid}/full").json()["error"]["code"] == "not_approved"
    principal.post(f"{API}/export/requests/{rid}/decide", json={"approve": True})
    assert admin.get(f"{API}/export/requests/{rid}/download").json()["error"]["code"] == "use_full_export"
    assert office.get(f"{API}/export/requests/{rid}/full").status_code == 403

    data, manifest = _browser_zip(admin, rid)
    names = {e["collection"] for e in manifest["collections"]}
    assert {"students", "ledger_entries", "users", "audit_log"} <= names
    assert not names & {"sessions", "login_codes", "password_resets", "rate_limits", "api_keys"}
    users_lines = zipfile.ZipFile(io.BytesIO(data)).read("collections/users.jsonl").decode()
    assert "password_hash" not in users_lines and '"mfa"' not in users_lines
    assert "## students" in manifest["dictionary_md"] and "`prn`" in manifest["dictionary_md"]
    assert db.audit_log.find_one({"action": "exports.full_started"})

    # Restore into a fresh database: same records, same types.
    target = db.client[RESTORE_DB]
    db.client.drop_database(RESTORE_DB)
    try:
        counts = restore(data, target)
        for name in names:
            if name != "audit_log":  # the export itself added audit entries after the pages were read
                assert counts[name] == db[name].count_documents({}), name
        assert check(data, target) == []
        assert ledger_total(target) == ledger_total(db)
        original = db.students.find_one({"prn": "2026BCA001"})
        restored = target.students.find_one({"_id": original["_id"]})
        assert restored == original  # ObjectIds, dates and nested fields come back exactly
        entry = db.ledger_entries.find_one({})
        if entry:
            assert target.ledger_entries.find_one({"_id": entry["_id"]}) == entry
        u = target.users.find_one({"prn": "2026BCA001"})
        assert u["password_hash"] is None and u["must_change_password"] is True
        assert "prn_1" in "".join(target.students.index_information())
        target.students.delete_one({"_id": original["_id"]})
        assert any(p.startswith("students:") and "missing" in p for p in check(data, target))
        try:
            restore(data, target)
        except SystemExit as e:
            assert "not empty" in str(e)
        else:
            raise AssertionError("restoring over data must refuse")
    finally:
        db.client.drop_database(RESTORE_DB)
