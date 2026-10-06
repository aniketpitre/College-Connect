from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.hostel import service
from app.modules.hostel.schemas import (
    AllotIn,
    BlockIn,
    ComplaintIn,
    ComplaintUpdate,
    MessMenu,
    OutpassAction,
    OutpassIn,
    RoomsIn,
    VacateIn,
)

router = APIRouter(tags=["hostel"])
MANAGE = Depends(require(P.HOSTEL_MANAGE))
READ = Depends(require(P.HOSTEL_READ))
ME = Depends(signed_in)


@router.get("/hostel")
def overview(ctx: AuthContext = READ) -> dict[str, Any]:
    return service.overview()


@router.post("/hostel/blocks", status_code=201)
def add_block(body: BlockIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_block(ctx, body)


@router.put("/hostel/blocks/{block_id}")
def update_block(block_id: str, body: BlockIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_block(ctx, block_id, body)


@router.post("/hostel/blocks/{block_id}/rooms")
def add_rooms(block_id: str, body: RoomsIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_rooms(ctx, block_id, body.numbers, body.beds)


@router.post("/hostel/allotments")
def allot(body: AllotIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.allot(ctx, body.prn, body.room_id, body.bed, client_ip(request))


@router.post("/hostel/allotments/{allotment_id}/vacate")
def vacate(allotment_id: str, body: VacateIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.vacate(ctx, allotment_id, body.reason, client_ip(request))


@router.get("/hostel/outpasses")
def outpasses(
    status: str = Query("requested", pattern="^(requested|active|returned|rejected)$"), ctx: AuthContext = READ
) -> list[dict[str, Any]]:
    return service.list_outpasses(status)


@router.post("/hostel/outpasses/{outpass_id}/action")
def act(outpass_id: str, body: OutpassAction, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.act_outpass(ctx, outpass_id, body.action, body.reason, client_ip(request))


@router.get("/hostel/complaints")
def complaints(
    status: str | None = Query(None, pattern="^(open|in_progress|resolved)$"), ctx: AuthContext = READ
) -> list[dict[str, Any]]:
    return service.list_complaints(status)


@router.patch("/hostel/complaints/{complaint_id}")
def update_complaint(complaint_id: str, body: ComplaintUpdate, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_complaint(ctx, complaint_id, body)


@router.put("/hostel/mess-menu")
def save_menu(body: MessMenu, ctx: AuthContext = MANAGE) -> dict[str, str]:
    return service.save_menu(ctx, body)


@router.get("/me/hostel")
def my_hostel(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_hostel(ctx)


@router.post("/me/hostel/outpasses", status_code=201)
def request_outpass(body: OutpassIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.request_outpass(ctx, body)


@router.post("/me/hostel/complaints", status_code=201)
def complain(body: ComplaintIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.complain(ctx, body)
