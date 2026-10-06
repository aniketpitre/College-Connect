from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.modules.eligibility import service
from app.modules.eligibility.schemas import IncomeIn, SchemeIn

router = APIRouter(tags=["scholarship eligibility"])
READ = Depends(require(P.FEES_READ))
MANAGE = Depends(require(P.FEES_MANAGE))


@router.get("/scholarship-schemes")
def schemes(ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.schemes()


@router.post("/scholarship-schemes", status_code=201)
def create(body: SchemeIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.save_scheme(ctx, body, create=True)


@router.put("/scholarship-schemes/{code}")
def update(code: str, body: SchemeIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.save_scheme(ctx, body.model_copy(update={"code": code}), create=False)


@router.get("/scholarship-schemes/{code}/candidates")
def candidates(code: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return service.candidates(code)


@router.get("/me/scholarship-check")
def mine(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.mine(ctx)


@router.put("/me/scholarship-check/income")
def declare_income(body: IncomeIn, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.declare_income(ctx, body)
