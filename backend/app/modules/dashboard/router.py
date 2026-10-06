from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, signed_in
from app.modules.dashboard import service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    """Staff home: the sections the signed-in person's roles allow (empty for students)."""
    if ctx.user.get("kind") != "staff":
        return {}
    return service.dashboard(ctx)
