from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.auth import AuthContext, require
from app.core.rbac import P
from app.modules.auditlog import service

router = APIRouter(tags=["audit"])


@router.get("/audit")
def audit_log(
    area: str | None = None,
    action: str | None = Query(None, max_length=80),
    actor: str | None = Query(None, max_length=100),
    target_id: str | None = Query(None, max_length=40),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    before: str | None = None,
    ctx: AuthContext = Depends(require(P.AUDIT_READ)),
) -> dict[str, Any]:
    return service.search(
        area=area,
        action=action,
        actor=actor,
        target_id=target_id,
        date_from=date_from,
        date_to=date_to,
        before=before,
    )
