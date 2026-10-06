"""Checks for the Phase 4 security review (docs/erp/security-review.md)."""

from dataclasses import replace

from fastapi.testclient import TestClient

from tests.conftest import login


def test_spoofed_forwarded_for_does_not_dodge_the_ip_limit(monkeypatch, client, make_user):
    from app.core import config
    from app.modules.auth import service

    monkeypatch.setattr(service, "settings", replace(config.settings, login_limit_per_ip=5))
    make_user()
    codes = [
        client.post(
            "/api/v1/auth/login",
            json={"identifier": "nobody@college.test", "password": "x"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(6)
    ]
    assert codes[-1] == 429  # a new X-Forwarded-For each time doesn't help
    assert login(client, "staff@college.test").status_code == 429  # same caller, still limited


def test_security_headers(client, make_user):
    make_user()
    r = login(client, "staff@college.test")
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert r.headers["strict-transport-security"].startswith("max-age=")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "camera=()" in r.headers["permissions-policy"]
    docs = client.get("/api/v1/docs")
    assert "content-security-policy" not in docs.headers  # the docs page loads its own scripts


def test_localhost_origins_only_off_vercel(monkeypatch):
    from app import main
    from app.core import config

    def preflight(allow: bool) -> str | None:
        monkeypatch.setattr(main, "settings", replace(config.settings, allow_localhost_origins=allow))
        c = TestClient(main.create_app())
        r = c.options(
            "/api/v1/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        return r.headers.get("access-control-allow-origin")

    assert preflight(True) == "http://localhost:5173"
    assert preflight(False) is None


def test_naac_intake_keys_must_be_programme_ids(client, sign_in, db):
    sign_in(client, ["iqac"])
    bad = client.put("/api/v1/reports/naac/settings", json={"intake": {"$where": 1}})
    assert bad.status_code == 422
    ok = client.put("/api/v1/reports/naac/settings", json={"intake": {"6ac4fa8a41773ae8c0ebd2a9": 60}})
    assert ok.status_code == 200
