from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthContext, any_session, optional_session, signed_in, signed_in_allow_password_change
from app.modules.auth import mfa, reset, service
from app.modules.auth.schemas import (
    CodeRequest,
    ForgotRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordConfirm,
    ResetRequest,
    SetupRequest,
)
from app.modules.users import repo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    return service.login(request, response, body.identifier, body.password)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, ctx: AuthContext | None = Depends(optional_session)) -> None:
    service.logout(request, response, ctx)


@router.post("/logout-all")
def logout_all(request: Request, response: Response, ctx: AuthContext = Depends(any_session)) -> dict:
    return {"signed_out_sessions": service.logout_everywhere(request, response, ctx)}


@router.get("/me")
def me(ctx: AuthContext = Depends(any_session)) -> dict:
    return repo.me_payload(ctx.user, ctx.session["state"])


@router.post("/password/change")
def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(signed_in_allow_password_change),
) -> dict:
    return service.change_password(request, response, ctx, body.current_password, body.new_password)


@router.get("/sessions")
def sessions(ctx: AuthContext = Depends(signed_in)) -> list[dict]:
    return service.my_sessions(ctx)


@router.delete("/sessions/{sid}", status_code=204)
def end_session(sid: str, request: Request, ctx: AuthContext = Depends(signed_in)) -> None:
    service.end_my_session(request, ctx, sid)


@router.get("/login-history")
def login_history(ctx: AuthContext = Depends(signed_in)) -> list[dict]:
    return service.login_history(ctx)


@router.get("/setup")
def setup_status() -> dict:
    return service.setup_status()


@router.post("/setup", status_code=201)
def setup(body: SetupRequest, request: Request) -> dict:
    return service.first_admin_setup(request, body.name, str(body.email), body.password, body.setup_token)


@router.post("/password/forgot")
def forgot_password(body: ForgotRequest, request: Request) -> dict:
    return reset.request_reset(request, body.identifier)


@router.post("/password/reset")
def reset_password(body: ResetRequest, request: Request) -> dict:
    return reset.complete_reset(request, body.token, body.new_password)


@router.get("/mfa")
def mfa_status(ctx: AuthContext = Depends(signed_in)) -> dict:
    return mfa.status(ctx)


@router.post("/mfa/setup")
def mfa_setup(ctx: AuthContext = Depends(any_session)) -> dict:
    return mfa.start_setup(ctx)


@router.post("/mfa/enable")
def mfa_enable(
    body: CodeRequest, request: Request, response: Response, ctx: AuthContext = Depends(any_session)
) -> dict:
    return mfa.enable(request, response, ctx, body.code)


@router.post("/mfa/verify")
def mfa_verify(
    body: CodeRequest, request: Request, response: Response, ctx: AuthContext = Depends(any_session)
) -> dict:
    return mfa.verify(request, response, ctx, body.code)


@router.post("/mfa/disable")
def mfa_disable(body: PasswordConfirm, request: Request, ctx: AuthContext = Depends(signed_in)) -> dict:
    return mfa.disable(request, ctx, body.password)


@router.post("/mfa/recovery-codes")
def mfa_recovery_codes(body: PasswordConfirm, request: Request, ctx: AuthContext = Depends(signed_in)) -> dict:
    return mfa.new_recovery_codes(request, ctx, body.password)
