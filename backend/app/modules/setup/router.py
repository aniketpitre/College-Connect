from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.setup import service
from app.modules.setup.schemas import (
    AcademicYearIn,
    AcademicYearUpdate,
    CategoryIn,
    CategoryUpdate,
    DepartmentIn,
    DepartmentUpdate,
    DivisionIn,
    DivisionUpdate,
    HolidayIn,
    HolidayUpdate,
    InstitutionSettings,
    ProgrammeIn,
    ProgrammeUpdate,
    SubjectIn,
    SubjectUpdate,
)

router = APIRouter(prefix="/setup", tags=["setup"])
READ = Depends(require(P.SETUP_READ))
MANAGE = Depends(require(P.SETUP_MANAGE))


@router.get("")
def overview(ctx: AuthContext = READ) -> dict[str, Any]:
    return service.overview()


@router.put("/institution")
def save_institution(body: InstitutionSettings, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.save_institution(ctx, body, client_ip(request))


@router.post("/starter-data")
def starter_data(request: Request, ctx: AuthContext = MANAGE) -> dict[str, int]:
    return service.load_starter_data(ctx, client_ip(request))


@router.post("/academic-years/{year_id}/make-current")
def make_current(year_id: str, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.make_current(ctx, year_id, client_ip(request))


@router.get("/subjects")
def subjects(
    programme_id: str | None = None, semester: int | None = Query(None, ge=1), ctx: AuthContext = READ
) -> list[dict[str, Any]]:
    return service.list_records("subjects", {"programme_id": programme_id, "semester": semester})


@router.get("/holidays")
def holidays(academic_year_id: str | None = None, ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.list_records("holidays", {"academic_year_id": academic_year_id})


def _crud(path: str, entity: str, create_model: type, update_model: type) -> None:
    """POST /setup/<path> and PATCH /setup/<path>/{id} for one kind of record."""

    def create_record(body: create_model, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:  # type: ignore[valid-type]
        return service.create(ctx, entity, body, client_ip(request))

    def update_record(
        record_id: str,
        body: update_model,  # type: ignore[valid-type]
        request: Request,
        ctx: AuthContext = MANAGE,
    ) -> dict[str, Any]:
        return service.update(ctx, entity, record_id, body, client_ip(request))

    router.add_api_route(f"/{path}", create_record, methods=["POST"], status_code=201, name=f"create_{entity}")
    router.add_api_route(f"/{path}/{{record_id}}", update_record, methods=["PATCH"], name=f"update_{entity}")


_crud("academic-years", "academic_years", AcademicYearIn, AcademicYearUpdate)
_crud("departments", "departments", DepartmentIn, DepartmentUpdate)
_crud("programmes", "programmes", ProgrammeIn, ProgrammeUpdate)
_crud("divisions", "divisions", DivisionIn, DivisionUpdate)
_crud("subjects", "subjects", SubjectIn, SubjectUpdate)
_crud("categories", "categories", CategoryIn, CategoryUpdate)
_crud("holidays", "holidays", HolidayIn, HolidayUpdate)
