from typing import Any

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.auth import AuthContext, require, signed_in
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.modules.placement import service
from app.modules.placement.schemas import DriveIn, ProfileIn, ResultIn

router = APIRouter(tags=["placement"])
MANAGE = Depends(require(P.PLACEMENT_MANAGE))
READ = Depends(require(P.PLACEMENT_READ))
ME = Depends(signed_in)


@router.get("/placement/drives")
def drives(ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.list_drives()


@router.post("/placement/drives", status_code=201)
def create(body: DriveIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_drive(ctx, body)


@router.put("/placement/drives/{drive_id}")
def update(drive_id: str, body: DriveIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_drive(ctx, drive_id, body)


@router.get("/placement/drives/{drive_id}/registrations")
def registrations(drive_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return service.registrations(drive_id)


@router.get("/placement/drives/{drive_id}/registrations.csv")
def registrations_csv(drive_id: str, ctx: AuthContext = MANAGE) -> Response:
    text, name = service.registrations_csv(drive_id)
    return Response(
        content=text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.post("/placement/drives/{drive_id}/results")
def results(drive_id: str, body: ResultIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.record_results(ctx, drive_id, body.registration_ids, body.action, body.ctc_lpa)


@router.get("/placement/registrations/{registration_id}/resume")
def resume(registration_id: str, ctx: AuthContext = MANAGE) -> Response:
    doc = service.resume_for(registration_id)
    return Response(
        content=bytes(doc["data"]),
        media_type=doc["content_type"],
        headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"', "Cache-Control": "private, no-store"},
    )


@router.get("/placement/stats")
def stats(ctx: AuthContext = READ) -> dict[str, Any]:
    return service.stats()


@router.get("/me/placement")
def mine(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_placement(ctx)


@router.put("/me/placement/profile")
def profile(body: ProfileIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.save_profile(ctx, body)


@router.post("/me/placement/resume")
async def upload_resume(file: UploadFile = File(...), ctx: AuthContext = ME) -> dict[str, Any]:
    data = await file.read(MAX_BYTES + 1)
    return service.upload_resume(ctx, file.filename or "resume.pdf", data)


@router.post("/me/placement/drives/{drive_id}/register")
def register(drive_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.register(ctx, drive_id)


@router.post("/me/placement/drives/{drive_id}/withdraw")
def withdraw(drive_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.withdraw(ctx, drive_id)
