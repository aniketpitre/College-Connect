from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.auth import AuthContext, require
from app.core.db import get_db
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.core.rbac import P
from app.core.requestinfo import base_url, client_ip
from app.modules.fees import approvals, cancellations, opening, receipt_pdf, receipts, reports, scholarships, service
from app.modules.fees.schemas import (
    CancelRequest,
    ChargeIn,
    CollectIn,
    ConcessionIn,
    Decision,
    FeeHeadIn,
    FeeHeadUpdate,
    GenerateDemands,
    RefundRequest,
    ScholarshipAction,
    ScholarshipIn,
    StructureIn,
    StructureUpdate,
)
from app.modules.setup import service as setup
from app.modules.students import service as students

router = APIRouter(tags=["fees"])
READ = Depends(require(P.FEES_READ))
MANAGE = Depends(require(P.FEES_MANAGE))
COLLECT = Depends(require(P.FEES_COLLECT))
DECIDE = Depends(require(P.APPROVALS_DECIDE))


def year_or_current(academic_year_id: str | None) -> Any:
    if academic_year_id:
        return service.oid(academic_year_id, "Academic year")
    current = get_db().academic_years.find_one({"is_current": True})
    if not current:
        raise AppError(409, "Set the current academic year in College setup.", "no_current_year")
    return current["_id"]


# --- fee heads and structures ---------------------------------------------------------------


@router.get("/fees/heads")
def heads(ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.list_heads()


@router.post("/fees/heads", status_code=201)
def create_head(body: FeeHeadIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_head(ctx, body, client_ip(request))


@router.post("/fees/heads/starter")
def starter_heads(request: Request, ctx: AuthContext = MANAGE) -> dict[str, int]:
    return service.load_starter_heads(ctx, client_ip(request))


@router.patch("/fees/heads/{head_id}")
def update_head(head_id: str, body: FeeHeadUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_head(ctx, head_id, body, client_ip(request))


@router.get("/fees/structures")
def structures(
    academic_year_id: str | None = None, programme_id: str | None = None, ctx: AuthContext = READ
) -> list[dict]:
    return service.list_structures(academic_year_id, programme_id)


@router.post("/fees/structures", status_code=201)
def create_structure(body: StructureIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_structure(ctx, body, client_ip(request))


@router.put("/fees/structures/{structure_id}")
def update_structure(structure_id: str, body: StructureUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict:
    return service.update_structure(ctx, structure_id, body, client_ip(request))


@router.post("/fees/demands/generate")
def generate(body: GenerateDemands, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.generate_demands(ctx, body, client_ip(request))


# --- a student's account --------------------------------------------------------------------


@router.get("/fees/students/{student_id}")
def account(student_id: str, academic_year_id: str | None = None, ctx: AuthContext = READ) -> dict[str, Any]:
    student = students.get_student(service.oid(student_id, "Student"))
    result = service.account(student["_id"], year_or_current(academic_year_id))
    result["student"] = students.summary(student)
    return result


@router.post("/fees/students/{student_id}/charges")
def add_charge(student_id: str, body: ChargeIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_charge(ctx, student_id, body, client_ip(request))


@router.post("/fees/students/{student_id}/late-fees")
def late_fees(
    student_id: str, request: Request, academic_year_id: str = Query(...), ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return service.apply_late_fees(ctx, student_id, academic_year_id, client_ip(request))


# --- concessions, scholarships and approvals -----------------------------------------------


@router.post("/fees/concessions", status_code=201)
def request_concession(body: ConcessionIn, request: Request, ctx: AuthContext = COLLECT) -> dict[str, Any]:
    return approvals.request_concession(ctx, body, client_ip(request))


@router.get("/fees/scholarships")
def list_scholarships(
    student_id: str | None = None, academic_year_id: str | None = None, ctx: AuthContext = READ
) -> list[dict]:
    return scholarships.list_for(student_id, academic_year_id)


@router.post("/fees/scholarships", status_code=201)
def create_scholarship(body: ScholarshipIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return scholarships.create(ctx, body, client_ip(request))


@router.post("/fees/scholarships/{scholarship_id}/actions")
def scholarship_action(
    scholarship_id: str, body: ScholarshipAction, request: Request, ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return scholarships.act(ctx, scholarship_id, body, client_ip(request))


@router.get("/approvals")
def list_approvals(
    status: str | None = Query("pending", pattern="^(pending|approved|rejected)$"),
    kind: str | None = None,
    student_id: str | None = None,
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return approvals.list_requests(status, student_id, kind)


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: str, body: Decision, request: Request, ctx: AuthContext = DECIDE) -> dict[str, Any]:
    return approvals.decide(ctx, approval_id, body.approve, body.reason, client_ip(request))


# --- collection and receipts ----------------------------------------------------------------


@router.post("/fees/collect", status_code=201)
def collect(body: CollectIn, request: Request, ctx: AuthContext = COLLECT) -> dict[str, Any]:
    return receipts.collect(ctx, body, client_ip(request))


@router.get("/fees/today")
def today(day: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), ctx: AuthContext = READ) -> dict[str, Any]:
    return receipts.today(day)


@router.get("/fees/receipts")
def list_receipts(
    date_from: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    student_id: str | None = None,
    number: str | None = Query(None, max_length=40),
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return receipts.list_receipts(date_from=date_from, date_to=date_to, student_id=student_id, number=number)


@router.get("/fees/receipts/{receipt_id}")
def get_receipt(receipt_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return receipts.view(receipts.get_receipt(receipt_id))


def receipt_pdf_response(
    receipt: dict[str, Any], original: bool, request: Request, label: str | None = None
) -> Response:
    """`label` overrides ORIGINAL/DUPLICATE (e.g. STUDENT COPY); a cancelled receipt always says CANCELLED."""
    copy = "CANCELLED" if receipt["status"] == "cancelled" else (label or ("ORIGINAL" if original else "DUPLICATE"))
    link = receipts.verify_url(base_url(request), receipt["verify_code"])
    data = receipt_pdf.build(receipt, setup.institution(), link, copy)
    filename = "receipt-" + receipt["number"].replace("/", "-") + ".pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.get("/fees/receipts/{receipt_id}/pdf")
def receipt_pdf_download(receipt_id: str, request: Request, ctx: AuthContext = READ) -> Response:
    receipt, first = receipts.take_print(receipt_id)
    return receipt_pdf_response(receipt, first, request)


@router.post("/fees/receipts/{receipt_id}/email")
def email_receipt(receipt_id: str, request: Request, ctx: AuthContext = COLLECT) -> dict[str, Any]:
    return receipts.email_receipt(ctx, receipt_id, base_url(request), client_ip(request))


# --- cancellations, refunds and the public Verify page --------------------------------------


@router.post("/fees/receipts/{receipt_id}/cancel-request", status_code=201)
def cancel_request(receipt_id: str, body: CancelRequest, request: Request, ctx: AuthContext = COLLECT) -> dict:
    return cancellations.request_cancel(ctx, receipt_id, body.reason, client_ip(request))


@router.post("/fees/refunds", status_code=201)
def refund_request(body: RefundRequest, request: Request, ctx: AuthContext = COLLECT) -> dict[str, Any]:
    return cancellations.request_refund(ctx, body, client_ip(request))


@router.get("/verify/{code}")
def verify(code: str, request: Request) -> dict[str, Any]:
    """Public: anyone holding a receipt (a bank, a scholarship office) can check it."""
    hit(f"verify:{client_ip(request)}", limit=60, window_seconds=3600)
    return cancellations.verify(code)


# --- opening balances and reports -----------------------------------------------------------

DAY = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/fees/opening/template.csv", response_class=PlainTextResponse)
def opening_template(ctx: AuthContext = MANAGE) -> PlainTextResponse:
    return PlainTextResponse(
        opening.template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="opening-balances.csv"'},
    )


@router.post("/fees/opening")
async def opening_import(
    request: Request,
    file: UploadFile = File(...),
    commit: bool = Query(False),
    academic_year_id: str | None = None,
    ctx: AuthContext = MANAGE,
) -> dict[str, Any]:
    data = await file.read(2 * 1024 * 1024 + 1)
    return opening.run(
        ctx, year_or_current(academic_year_id), file.filename or "opening", data, commit, client_ip(request)
    )


@router.get("/fees/reports/{name}", response_model=None)
def report(
    name: str,
    date_from: str | None = Query(None, pattern=DAY),
    date_to: str | None = Query(None, pattern=DAY),
    as_of: str | None = Query(None, pattern=DAY),
    academic_year_id: str | None = None,
    programme_id: str | None = None,
    year_of_study: int | None = Query(None, ge=1, le=6),
    format: str = Query("json", pattern="^(json|xlsx)$"),
    ctx: AuthContext = READ,
) -> dict[str, Any] | Response:
    year_id = year_or_current(academic_year_id) if name in {"outstanding", "defaulters", "scholarships"} else None
    data = reports.build(
        name,
        {
            "date_from": date_from,
            "date_to": date_to,
            "as_of": as_of,
            "year_id": year_id,
            "programme_id": programme_id,
            "year_of_study": year_of_study,
        },
    )
    if format == "json":
        return reports.to_json(data)
    period = f"{date_from} to {date_to or date_from}" if date_from else ""
    college = setup.institution().get("name") or "CollegeConnect"
    content = reports.to_xlsx(data, " · ".join(x for x in (college, period) if x))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}-{date_from or "current"}.xlsx"'},
    )
