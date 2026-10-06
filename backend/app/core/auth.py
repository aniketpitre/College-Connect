"""
Sessions and the "who is calling" dependencies.

A session is a random token in an HttpOnly cookie; MongoDB stores only its SHA-256 hash.
Session states:
  active             signed in
  mfa_pending        password correct, waiting for the 2-step code
  mfa_setup          password correct, role requires 2-step verification that isn't set up yet
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import Depends, Request, Response
from pymongo import IndexModel

from app.core.config import settings
from app.core.db import get_db, register_indexes
from app.core.errors import AppError
from app.core.rbac import P, permissions_for
from app.core.requestinfo import client_ip, user_agent
from app.core.security import new_token, token_hash

COOKIE_NAME = "cc_session"
CSRF_HEADER = "X-Requested-With"
CHILD_HEADER = "X-Child"

STAFF_SESSION = timedelta(hours=12)
STUDENT_SESSION = timedelta(days=30)
PARTIAL_SESSION = timedelta(minutes=10)  # mfa_pending / mfa_setup
LAST_SEEN_RESOLUTION = timedelta(minutes=5)

register_indexes(
    "sessions",
    [
        IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        IndexModel([("user_id", 1)]),
        IndexModel([("sid", 1)], unique=True),
    ],
)


@dataclass
class AuthContext:
    user: dict[str, Any]
    session: dict[str, Any]
    child_id: str | None = None  # parents: the child this request is about (X-Child header)

    @property
    def user_id(self) -> ObjectId:
        return self.user["_id"]

    @property
    def permissions(self) -> frozenset[P]:
        return permissions_for(self.user.get("roles", []))


def session_lifetime(user: dict[str, Any], state: str) -> timedelta:
    if state != "active":
        return PARTIAL_SESSION
    return STUDENT_SESSION if user.get("kind") in {"student", "parent"} else STAFF_SESSION


def create_session(response: Response, request: Request, user: dict[str, Any], state: str) -> dict[str, Any]:
    token = new_token()
    now = datetime.now(UTC)
    lifetime = session_lifetime(user, state)
    session = {
        "_id": token_hash(token),
        "sid": secrets.token_urlsafe(12),  # public id, shown in "your devices"
        "user_id": user["_id"],
        "state": state,
        "created_at": now,
        "last_seen_at": now,
        "expires_at": now + lifetime,
        "ip": client_ip(request),
        "user_agent": user_agent(request),
    }
    get_db().sessions.insert_one(session)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return session


def end_session(response: Response, session: dict[str, Any] | None) -> None:
    if session:
        get_db().sessions.delete_one({"_id": session["_id"]})
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


def revoke_user_sessions(user_id: ObjectId, *, keep_session_id: str | None = None) -> int:
    query: dict[str, Any] = {"user_id": user_id}
    if keep_session_id:
        query["_id"] = {"$ne": keep_session_id}
    return get_db().sessions.delete_many(query).deleted_count


def _load(request: Request) -> AuthContext | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    db = get_db()
    now = datetime.now(UTC)
    session = db.sessions.find_one({"_id": token_hash(token), "expires_at": {"$gt": now}})
    if not session:
        return None
    user = db.users.find_one({"_id": session["user_id"]})
    if not user or user.get("status") == "disabled":
        db.sessions.delete_one({"_id": session["_id"]})
        return None
    if now - session["last_seen_at"] > LAST_SEEN_RESOLUTION:
        db.sessions.update_one({"_id": session["_id"]}, {"$set": {"last_seen_at": now}})
    child = request.headers.get(CHILD_HEADER) if user.get("kind") == "parent" else None
    return AuthContext(user=user, session=session, child_id=child or None)


def optional_session(request: Request) -> AuthContext | None:
    return _load(request)


def any_session(request: Request) -> AuthContext:
    """Signed in, in any state (used by /me, logout and the 2-step screens)."""
    ctx = _load(request)
    if ctx is None:
        raise AppError(401, "Please sign in.", "not_signed_in")
    return ctx


def signed_in_allow_password_change(ctx: AuthContext = Depends(any_session)) -> AuthContext:
    """Fully signed in; a pending forced password change is allowed (for the change-password call)."""
    state = ctx.session["state"]
    if state == "mfa_pending":
        raise AppError(401, "Enter your 2-step verification code.", "mfa_required")
    if state == "mfa_setup":
        raise AppError(401, "Set up 2-step verification to continue.", "mfa_setup_required")
    return ctx


def signed_in(request: Request, ctx: AuthContext = Depends(signed_in_allow_password_change)) -> AuthContext:
    if ctx.user.get("must_change_password"):
        raise AppError(403, "Set a new password to continue.", "password_change_required")
    if ctx.user.get("read_only") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        # After a TC the former student can still sign in to read and download, but not change anything.
        raise AppError(403, "Your account is read-only: you have left the college.", "read_only")
    if ctx.user.get("kind") == "parent":
        _parent_guard(request, ctx)
    return ctx


def _parent_guard(request: Request, ctx: AuthContext) -> None:
    from app.modules.parents import guard
    from app.modules.parents import service as parents

    route = request.scope.get("route")
    needs_child, area = guard.area_for(request.method, getattr(route, "path", request.url.path))
    if needs_child:
        parents.child(ctx)  # the child must be theirs
        if area:
            parents.check_area(ctx, area)


def require(permission: P):
    def dependency(ctx: AuthContext = Depends(signed_in)) -> AuthContext:
        if permission not in ctx.permissions:
            raise AppError(403, "You don't have permission to do this.", "forbidden")
        return ctx

    return dependency


async def csrf_guard(request: Request, call_next):
    """
    Cookie-authenticated requests that change data must carry the X-Requested-With header.

    Browsers never add custom headers to cross-site form posts, so a forged request from
    another site is rejected even though SameSite=Lax would already block most of them.
    """
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.cookies.get(COOKIE_NAME)
        and not request.headers.get(CSRF_HEADER)
    ):
        from fastapi.responses import JSONResponse

        from app.core.errors import error_body

        return JSONResponse(error_body("csrf_failed", "Request blocked (missing security header)."), status_code=403)
    return await call_next(request)
