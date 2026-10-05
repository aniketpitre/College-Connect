from typing import Any

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.core.auth import AuthContext, signed_in
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.marks import guard, service
from app.modules.marks.schemas import SchemeIn, SheetAction, SheetSave

router = APIRouter(tags=["marks"])
STAFF_MARKS = {P.MARKS_ENTER, P.MARKS_APPROVE, P.MARKS_SCHEME_DEPT, P.MARKS_READ, P.EXAMS_MANAGE}


def _staff(ctx: AuthContext = Depends(signed_in)) -> AuthContext:
    if not ctx.permissions & STAFF_MARKS:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return ctx


STAFF = Depends(_staff)


@router.get("/marks/schemes")
def schemes(
    programme_id: str, semester: int | None = None, academic_year_id: str | None = None, ctx: AuthContext = STAFF
) -> list[dict[str, Any]]:
    return service.list_schemes(ctx, programme_id, semester, academic_year_id)


@router.put("/marks/schemes")
def save_scheme(body: SchemeIn, request: Request, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.save_scheme(ctx, body, client_ip(request))


@router.get("/marks/my-classes")
def my_classes(ctx: AuthContext = STAFF) -> list[dict[str, Any]]:
    return service.my_classes(ctx)


@router.get("/marks/overview")
def overview(ctx: AuthContext = STAFF) -> list[dict[str, Any]]:
    return service.department_sheets(ctx)


@router.get("/marks/sheet")
def sheet(division_id: str, subject_id: str, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.sheet(ctx, division_id, subject_id)


@router.put("/marks/sheet")
def save(body: SheetSave, request: Request, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.save(ctx, body, client_ip(request))


@router.post("/marks/sheet/action")
def act(body: SheetAction, request: Request, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return service.act(ctx, body, client_ip(request))


@router.get("/me/marks")
def my_marks(ctx: AuthContext = Depends(signed_in)) -> list[dict[str, Any]]:
    return service.my_marks(ctx)


@router.get("/marks/guard")
def guard_dashboard(ctx: AuthContext = STAFF) -> dict[str, Any]:
    return guard.dashboard(ctx)


@router.get("/marks/guard/detail")
def guard_detail(division_id: str, subject_id: str, ctx: AuthContext = STAFF) -> dict[str, Any]:
    return guard.detail(ctx, division_id, subject_id)


@router.get("/marks/guard/export")
def guard_export(division_id: str, subject_id: str, ctx: AuthContext = STAFF) -> Response:
    filename, data = guard.export_csv(ctx, division_id, subject_id)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.post("/marks/guard/check-file")
async def guard_check_file(
    division_id: str, subject_id: str, file: UploadFile = File(...), ctx: AuthContext = STAFF
) -> dict[str, Any]:
    data = await file.read(2_000_001)
    if len(data) > 2_000_000:
        raise AppError(413, "The file is too large (2 MB at most).", "too_large")
    return guard.check_file(ctx, division_id, subject_id, data)
