"""
2-step verification with an authenticator app (TOTP, RFC 6238) and one-time recovery codes.

The TOTP secret is stored encrypted (APP_SECRET_KEY); recovery codes are stored as SHA-256 hashes.
A code can be used only once: the last accepted time step is recorded, and a recovery code is
removed when used.
"""

import secrets
from datetime import UTC, datetime
from typing import Any

import pyotp
import segno
from fastapi import Request, Response

from app.core import audit
from app.core.auth import AuthContext, create_session, end_session, revoke_user_sessions
from app.core.db import get_db
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.rbac import mfa_required
from app.core.requestinfo import client_ip
from app.core.security import decrypt_secret, encrypt_secret, token_hash, verify_password
from app.modules.users import repo

ISSUER = "CollegeConnect"
RECOVERY_CODE_COUNT = 8
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
WRONG_CODE = "That code is not correct. Check the time on your phone and try again."


def _recovery_codes() -> list[str]:
    def one() -> str:
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        return f"{raw[:5]}-{raw[5:]}"

    return [one() for _ in range(RECOVERY_CODE_COUNT)]


def _normalize_recovery(code: str) -> str:
    raw = "".join(ch for ch in code.lower() if ch.isalnum())
    return f"{raw[:5]}-{raw[5:]}"


def _matching_step(secret: str, code: str) -> int | None:
    """The time step the code belongs to (current step ±1 to allow for clock drift), or None."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now = datetime.now(UTC)
    current = totp.timecode(now)
    for step in (current - 1, current, current + 1):
        if secrets.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def _account_label(user: dict[str, Any]) -> str:
    return user.get("email") or user.get("prn") or user["name"]


def _upgrade_session(request: Request, response: Response, ctx: AuthContext) -> None:
    """A partial session becomes a full one with a fresh token (the old token stops working)."""
    end_session(response, ctx.session)
    create_session(response, request, ctx.user, "active")


def start_setup(ctx: AuthContext) -> dict[str, Any]:
    if ctx.session["state"] == "mfa_pending":
        raise AppError(401, "Enter your 2-step verification code first.", "mfa_required")
    if ctx.user.get("mfa", {}).get("enabled"):
        raise AppError(409, "2-step verification is already on.", "conflict")
    secret = pyotp.random_base32()
    get_db().users.update_one({"_id": ctx.user_id}, {"$set": {"mfa.pending_secret": encrypt_secret(secret)}})
    uri = pyotp.TOTP(secret).provisioning_uri(name=_account_label(ctx.user), issuer_name=ISSUER)
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_svg": segno.make(uri, error="m").svg_data_uri(scale=5, border=2),
    }


def enable(request: Request, response: Response, ctx: AuthContext, code: str) -> dict[str, Any]:
    if ctx.session["state"] == "mfa_pending":
        raise AppError(401, "Enter your 2-step verification code first.", "mfa_required")
    hit(f"mfa:{ctx.user_id}", limit=10, window_seconds=15 * 60)
    mfa = ctx.user.get("mfa", {})
    if mfa.get("enabled"):
        raise AppError(409, "2-step verification is already on.", "conflict")
    if not mfa.get("pending_secret"):
        raise AppError(409, "Start the set-up again.", "conflict")
    secret = decrypt_secret(mfa["pending_secret"])
    step = _matching_step(secret, code)
    if step is None:
        raise AppError(400, WRONG_CODE, "invalid_code", "code")
    codes = _recovery_codes()
    now = datetime.now(UTC)
    new_mfa = {
        "enabled": True,
        "secret": mfa["pending_secret"],
        "last_step": step,
        "recovery_codes": [token_hash(c) for c in codes],
        "enabled_at": now,
    }
    get_db().users.update_one({"_id": ctx.user_id}, {"$set": {"mfa": new_mfa}})
    ctx.user["mfa"] = new_mfa
    audit.record("auth.mfa.enabled", actor_id=ctx.user_id, ip=client_ip(request))
    # Every session (other devices signed in before 2-step was on, and this one) is replaced
    # by one fresh, fully signed-in session for this device.
    revoke_user_sessions(ctx.user_id)
    create_session(response, request, ctx.user, "active")
    state = "active"
    return {"recovery_codes": codes, "me": repo.me_payload(ctx.user, state)}


def verify(request: Request, response: Response, ctx: AuthContext, code: str) -> dict[str, Any]:
    if ctx.session["state"] != "mfa_pending":
        raise AppError(409, "No 2-step code is needed right now.", "conflict")
    hit(f"mfa:{ctx.user_id}", limit=10, window_seconds=15 * 60, message="Too many wrong codes. Sign in again later.")
    ip = client_ip(request)
    mfa = ctx.user.get("mfa", {})
    db = get_db()
    method = "app"
    step = _matching_step(decrypt_secret(mfa["secret"]), code) if mfa.get("secret") else None
    if step is not None:
        # Atomic: a code (time step) already used is refused, even by a parallel request.
        accepted = db.users.update_one(
            {"_id": ctx.user_id, "mfa.last_step": {"$lt": step}}, {"$set": {"mfa.last_step": step}}
        ).modified_count
    else:
        method = "recovery_code"
        accepted = db.users.update_one(
            {"_id": ctx.user_id, "mfa.recovery_codes": token_hash(_normalize_recovery(code))},
            {"$pull": {"mfa.recovery_codes": token_hash(_normalize_recovery(code))}},
        ).modified_count
    if not accepted:
        audit.record("auth.mfa.failed", actor_id=ctx.user_id, ip=ip)
        raise AppError(400, WRONG_CODE, "invalid_code", "code")
    _upgrade_session(request, response, ctx)
    audit.record("auth.mfa.verified", actor_id=ctx.user_id, ip=ip, details={"method": method})
    user = repo.get_user(ctx.user_id)
    payload = repo.me_payload(user, "active")
    payload["recovery_codes_left"] = len(user.get("mfa", {}).get("recovery_codes", []))
    return payload


def _check_password(ctx: AuthContext, password: str) -> None:
    hit(f"pwcheck:{ctx.user_id}", limit=10, window_seconds=15 * 60)
    if not verify_password(ctx.user.get("password_hash"), password):
        raise AppError(400, "Your password is wrong.", "invalid_credentials", "password")


def disable(request: Request, ctx: AuthContext, password: str) -> dict[str, Any]:
    if mfa_required(ctx.user.get("roles", [])):
        raise AppError(403, "2-step verification is required for your role and can't be turned off.", "forbidden")
    if not ctx.user.get("mfa", {}).get("enabled"):
        raise AppError(409, "2-step verification is already off.", "conflict")
    _check_password(ctx, password)
    get_db().users.update_one({"_id": ctx.user_id}, {"$unset": {"mfa": ""}})
    ctx.user.pop("mfa", None)
    audit.record("auth.mfa.disabled", actor_id=ctx.user_id, ip=client_ip(request))
    return repo.me_payload(ctx.user, "active")


def new_recovery_codes(request: Request, ctx: AuthContext, password: str) -> dict[str, Any]:
    if not ctx.user.get("mfa", {}).get("enabled"):
        raise AppError(409, "Turn on 2-step verification first.", "conflict")
    _check_password(ctx, password)
    codes = _recovery_codes()
    get_db().users.update_one({"_id": ctx.user_id}, {"$set": {"mfa.recovery_codes": [token_hash(c) for c in codes]}})
    audit.record("auth.mfa.recovery_codes_replaced", actor_id=ctx.user_id, ip=client_ip(request))
    return {"recovery_codes": codes}


def status(ctx: AuthContext) -> dict[str, Any]:
    mfa = ctx.user.get("mfa", {})
    return {
        "enabled": bool(mfa.get("enabled")),
        "required": mfa_required(ctx.user.get("roles", [])),
        "recovery_codes_left": len(mfa.get("recovery_codes", [])),
        "enabled_at": mfa["enabled_at"].isoformat() if mfa.get("enabled_at") else None,
    }
