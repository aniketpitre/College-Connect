from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.core import clock
from app.core.auth import AuthContext, require, signed_in
from app.core.errors import AppError
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.students import service as students
from app.modules.timetable import service
from app.modules.timetable.schemas import ChangeIn, SlotIn, TimetableIn, TimetableUpdate

router = APIRouter(tags=["timetable"])
READ = Depends(require(P.TIMETABLE_READ))


def _manager(ctx: AuthContext = Depends(signed_in)) -> AuthContext:
    if P.TIMETABLE_MANAGE not in ctx.permissions and P.TIMETABLE_MANAGE_DEPT not in ctx.permissions:
        raise AppError(403, "You don't have permission to do this.", "forbidden")
    return ctx


MANAGE = Depends(_manager)


@router.get("/timetables")
def list_timetables(
    academic_year_id: str | None = None, division_id: str | None = None, ctx: AuthContext = READ
) -> list[dict[str, Any]]:
    return service.list_timetables(ctx, academic_year_id, division_id)


@router.post("/timetables", status_code=201)
def create_timetable(body: TimetableIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_timetable(ctx, body, client_ip(request))


@router.get("/timetables/{timetable_id}")
def get_timetable(timetable_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return service.view(service.get_timetable(timetable_id), ctx)


@router.patch("/timetables/{timetable_id}")
def update_timetable(
    timetable_id: str, body: TimetableUpdate, request: Request, ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return service.update_timetable(ctx, timetable_id, body, client_ip(request))


@router.get("/timetables/{timetable_id}/options")
def options(timetable_id: str, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.options(timetable_id)


@router.post("/timetables/{timetable_id}/slots", status_code=201)
def add_slot(timetable_id: str, body: SlotIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_slot(ctx, timetable_id, body, client_ip(request))


@router.put("/timetable-slots/{slot_id}")
def update_slot(slot_id: str, body: SlotIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_slot(ctx, slot_id, body, client_ip(request))


@router.delete("/timetable-slots/{slot_id}", status_code=204)
def remove_slot(slot_id: str, request: Request, ctx: AuthContext = MANAGE) -> Response:
    service.remove_slot(ctx, slot_id, client_ip(request))
    return Response(status_code=204)


@router.post("/timetable-slots/{slot_id}/changes", status_code=201)
def set_change(slot_id: str, body: ChangeIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.set_change(ctx, slot_id, body, client_ip(request))


@router.delete("/timetable-slots/{slot_id}/changes/{day}", status_code=204)
def remove_change(slot_id: str, day: date, request: Request, ctx: AuthContext = MANAGE) -> Response:
    service.remove_change(ctx, slot_id, day, client_ip(request))
    return Response(status_code=204)


@router.get("/timetable/week")
def week(
    division_id: str | None = None, mine: bool = False, day: date | None = None, ctx: AuthContext = READ
) -> dict[str, Any]:
    """One week (Mon–Sat) of a division's lectures, or (mine=true) the signed-in teacher's own."""
    start = day or clock.today()
    if mine:
        return service.week(start, faculty_id=ctx.user_id)
    if not division_id:
        raise AppError(422, "Choose a division.", field="division_id")
    return service.week(start, division_ids=[service.oid(division_id, "Division", "division_id")])


@router.get("/me/timetable")
def my_timetable(day: date | None = None, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    student = students.my_student(ctx)
    if not student.get("division_id"):
        raise AppError(404, "You haven't been placed in a division yet.", "no_division")
    return service.week(day or clock.today(), division_ids=[student["division_id"]])
