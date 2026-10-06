from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from app.core.auth import AuthContext, require
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.reports import government, naac
from app.modules.reports.schemas import NaacSettings

router = APIRouter(tags=["reports"])
READ = Depends(require(P.REPORTS_READ))
MANAGE = Depends(require(P.NAAC_MANAGE))
YEAR = Query(None, max_length=40)


def _csv(text: str, name: str) -> Response:
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"},
    )


@router.get("/reports/naac")
def aqar(year_id: str | None = YEAR, ctx: AuthContext = READ) -> dict[str, Any]:
    return naac.aqar(year_id)


@router.put("/reports/naac/settings")
def save_settings(body: NaacSettings, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return naac.save_settings(ctx, body)


@router.get("/reports/naac/{metric_id}.csv")
def metric_csv(metric_id: str, year_id: str | None = YEAR, ctx: AuthContext = READ) -> Response:
    return _csv(*naac.metric_csv(metric_id, year_id))


@router.post("/reports/naac/{metric_id}/evidence", status_code=201)
async def add_evidence(
    metric_id: str,
    file: UploadFile = File(...),
    title: str = Form("", max_length=120),
    year_id: str | None = Form(None),
    ctx: AuthContext = MANAGE,
) -> dict[str, Any]:
    data = await file.read()
    return naac.add_evidence(ctx, metric_id, year_id, title, data, file.filename or "evidence")


@router.get("/reports/naac/evidence/{evidence_id}")
def evidence(evidence_id: str, ctx: AuthContext = READ) -> Response:
    f = naac.evidence_file(evidence_id)
    return Response(
        content=bytes(f["data"]),
        media_type=f["content_type"],
        headers={"Content-Disposition": f'inline; filename="{f["filename"]}"', "Cache-Control": "private, no-store"},
    )


@router.delete("/reports/naac/evidence/{evidence_id}", status_code=204)
def remove_evidence(evidence_id: str, ctx: AuthContext = MANAGE) -> Response:
    naac.remove_evidence(ctx, evidence_id)
    return Response(status_code=204)


@router.get("/reports/aishe")
def aishe(year_id: str | None = YEAR, ctx: AuthContext = READ) -> dict[str, Any]:
    return government.aishe(year_id)


@router.get("/reports/aishe/{part}.csv")
def aishe_csv(part: str, year_id: str | None = YEAR, ctx: AuthContext = READ) -> Response:
    return _csv(*government.aishe_csv(year_id, "staff" if part == "staff" else "students"))


@router.get("/reports/nirf")
def nirf(year_id: str | None = YEAR, ctx: AuthContext = READ) -> dict[str, Any]:
    return government.nirf(year_id)


@router.get("/reports/nirf.csv")
def nirf_csv(year_id: str | None = YEAR, ctx: AuthContext = READ) -> Response:
    return _csv(*government.nirf_csv(year_id))


@router.get("/reports/apaar")
def apaar(ctx: AuthContext = READ) -> dict[str, Any]:
    return government.apaar_check()


@router.post("/reports/apaar/import")
async def import_apaar(
    request: Request, file: UploadFile = File(...), ctx: AuthContext = Depends(require(P.STUDENTS_MANAGE))
) -> dict[str, Any]:
    return government.import_apaar(ctx, await file.read(), client_ip(request))


@router.get("/reports/apaar/credits")
def credits(year_id: str | None = YEAR, ctx: AuthContext = READ) -> dict[str, Any]:
    return government.credits_preview(year_id)


@router.get("/reports/apaar/credits.csv")
def credits_csv(year_id: str | None = YEAR, ctx: AuthContext = READ) -> Response:
    return _csv(*government.credits_csv(ctx, year_id))
