from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthContext, signed_in
from app.modules.fees import statement_pdf
from app.modules.fees.router import receipt_pdf_response
from app.modules.portal import service
from app.modules.setup import service as setup

router = APIRouter(prefix="/me", tags=["student portal"])
ME = Depends(signed_in)


@router.get("/home")
def home(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.home(ctx)


@router.get("/fees")
def my_fees(academic_year_id: str | None = None, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_fees(ctx, academic_year_id)


@router.get("/receipts/{receipt_id}/pdf")
def my_receipt_pdf(receipt_id: str, request: Request, ctx: AuthContext = ME) -> Response:
    # The student's download is always a copy; it never uses up the ORIGINAL print.
    return receipt_pdf_response(service.my_receipt(ctx, receipt_id), False, request, label="STUDENT COPY")


@router.get("/fees/statement.pdf")
def my_statement(academic_year_id: str | None = None, ctx: AuthContext = ME) -> Response:
    student, year_name, account = service.statement(ctx, academic_year_id)
    data = statement_pdf.build(student, year_name, account, setup.institution())
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="fee-statement-{student["prn"]}-{year_name}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
