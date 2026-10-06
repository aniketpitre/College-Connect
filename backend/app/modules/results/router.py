from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, signed_in
from app.core.requestinfo import client_ip
from app.modules.results import result_pdf, service
from app.modules.setup import service as setup

router = APIRouter(tags=["results"])
ME = Depends(signed_in)


class PublishIn(BaseModel):
    publish: bool
    revaluation_days: int = Field(10, ge=0, le=60)


class RevalIn(BaseModel):
    code: str = Field(..., max_length=20)


class RevalDecision(BaseModel):
    status: Literal["forwarded", "changed", "unchanged"]
    external: float | None = None
    total: float | None = None
    grade: str | None = Field(None, max_length=4)
    grade_point: float | None = Field(None, ge=0, le=10)


@router.post("/exams/sessions/{session_id}/results/import")
async def import_results(
    session_id: str, request: Request, dry_run: bool = True, file: UploadFile = File(...), ctx: AuthContext = ME
) -> dict[str, Any]:
    data = await file.read(2_000_001)
    return service.import_results(ctx, session_id, file.filename or "results.csv", data, dry_run, client_ip(request))


@router.get("/exams/sessions/{session_id}/results")
def results(session_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.summary(ctx, session_id)


@router.post("/exams/sessions/{session_id}/results/publish")
def publish(session_id: str, body: PublishIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.publish(ctx, session_id, body.publish, body.revaluation_days, client_ip(request))


@router.get("/results/revaluations")
def revaluations(status: str | None = None, ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.list_revaluations(ctx, status)


@router.post("/results/revaluations/{reval_id}/decide")
def decide(reval_id: str, body: RevalDecision, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.decide_revaluation(ctx, reval_id, body.model_dump(), client_ip(request))


@router.get("/me/results")
def my_results(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_results(ctx)


@router.post("/me/results/{result_id}/revaluation")
def revaluation(result_id: str, body: RevalIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.request_revaluation(ctx, result_id, body.code, client_ip(request))


@router.get("/me/results/{result_id}.pdf")
def my_result_pdf(result_id: str, ctx: AuthContext = ME) -> Response:
    r, session, student = service.my_result(ctx, result_id)
    data = result_pdf.build(r, session, student, setup.institution(), service.standing(student["_id"])["cgpa"])
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="result-{student["prn"]}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
