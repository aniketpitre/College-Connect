from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthContext, require, signed_in
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.library import service
from app.modules.library.schemas import BookIn, CopiesIn, IssueIn, LostIn, ReserveIn, ReturnIn, SettingsIn

router = APIRouter(tags=["library"])
MANAGE = Depends(require(P.LIBRARY_MANAGE))
READ = Depends(require(P.LIBRARY_READ))
ME = Depends(signed_in)


@router.get("/library/books")
def books(q: str | None = Query(None, max_length=80), ctx: AuthContext = ME) -> list[dict[str, Any]]:
    """The catalogue: everyone signed in can search it (staff see the copies)."""
    return service.search(q, staff=P.LIBRARY_READ in ctx.permissions)


@router.get("/library/isbn/{isbn}")
def isbn(isbn: str, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.lookup_isbn(isbn.replace("-", "").strip())


@router.post("/library/books", status_code=201)
def add_book(body: BookIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_book(ctx, body)


@router.post("/library/books/{book_id}/copies")
def add_copies(book_id: str, body: CopiesIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_copies(ctx, book_id, body.count, body.barcodes)


@router.post("/library/issue")
def issue(body: IssueIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.issue(ctx, body.barcode, body.prn, client_ip(request))


@router.post("/library/return")
def return_book(body: ReturnIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.return_book(ctx, body.barcode, client_ip(request))


@router.post("/library/loans/{loan_id}/renew")
def renew(loan_id: str, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.renew(ctx, loan_id, own=False)


@router.post("/library/loans/{loan_id}/lost")
def lost(loan_id: str, body: LostIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.mark_lost(ctx, loan_id, body.price, client_ip(request))


@router.get("/library/loans")
def loans(
    status: str = Query("open", pattern="^(open|overdue|returned)$"),
    q: str | None = Query(None, max_length=40),
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return service.loans(status=status, q=q)


@router.get("/library/overview")
def overview(ctx: AuthContext = READ) -> dict[str, Any]:
    return service.overview()


@router.put("/library/settings")
def save_settings(body: SettingsIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.save_settings(ctx, body)


@router.get("/me/library")
def my_library(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_library(ctx)


@router.post("/me/library/reservations")
def reserve(body: ReserveIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.reserve(ctx, body.book_id)


@router.delete("/me/library/reservations/{reservation_id}")
def cancel(reservation_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.cancel_reservation(ctx, reservation_id)


@router.post("/me/library/loans/{loan_id}/renew")
def renew_mine(loan_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.renew(ctx, loan_id, own=True)
