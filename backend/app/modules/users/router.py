from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.users import repo, service
from app.modules.users.schemas import ReasonBody, UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/roles")
def roles(ctx: AuthContext = Depends(require(P.USERS_READ))) -> list[dict]:
    return service.role_catalog()


@router.get("")
def list_users(
    search: str | None = Query(None, max_length=100),
    kind: Literal["staff", "student", "parent"] | None = None,
    role: str | None = Query(None, max_length=40),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: AuthContext = Depends(require(P.USERS_READ)),
) -> dict:
    return service.list_users(ctx, search=search, kind=kind, role=role, skip=skip, limit=limit)


@router.get("/{user_id}")
def get_user(user_id: str, ctx: AuthContext = Depends(require(P.USERS_READ))) -> dict:
    return repo.public_user(repo.get_user(repo.parse_id(user_id)))


@router.post("", status_code=201)
def create_user(body: UserCreate, request: Request, ctx: AuthContext = Depends(require(P.USERS_READ))) -> dict:
    return service.create(ctx, body, client_ip(request))


@router.patch("/{user_id}")
def update_user(
    user_id: str, body: UserUpdate, request: Request, ctx: AuthContext = Depends(require(P.USERS_UPDATE))
) -> dict:
    return service.update(ctx, repo.parse_id(user_id), body, client_ip(request))


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str, body: ReasonBody, request: Request, ctx: AuthContext = Depends(require(P.USERS_READ))
) -> dict:
    return service.reset_password(ctx, repo.parse_id(user_id), body.reason, client_ip(request))


@router.post("/{user_id}/unlock")
def unlock(user_id: str, request: Request, ctx: AuthContext = Depends(require(P.USERS_UPDATE))) -> dict:
    return service.unlock(ctx, repo.parse_id(user_id), client_ip(request))


@router.post("/{user_id}/reset-2-step")
def reset_mfa(
    user_id: str, body: ReasonBody, request: Request, ctx: AuthContext = Depends(require(P.USERS_READ))
) -> dict:
    return service.reset_mfa(ctx, repo.parse_id(user_id), body.reason, client_ip(request))
