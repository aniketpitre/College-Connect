from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from app.core.auth import AuthContext, require, signed_in
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.admissions import merit, service
from app.modules.admissions.schemas import (
    ApplicationIn,
    CancelIn,
    CodeIn,
    ConfirmIn,
    CycleIn,
    CycleUpdate,
    Decision,
    DocumentDecision,
    EnquiryIn,
    EnquiryStatus,
    EnquiryUpdate,
    FeeIn,
    PhoneIn,
    RoundIn,
    StaffEnquiryIn,
    StartIn,
)
from app.modules.payments.router import ConfirmIn as PaymentConfirm
from app.modules.students.schemas import DocumentType

router = APIRouter(tags=["admissions"])
READ = Depends(require(P.ADMISSIONS_READ))
MANAGE = Depends(require(P.ADMISSIONS_MANAGE))
ME = Depends(signed_in)


# --- public: apply and enquire --------------------------------------------------------------


@router.get("/admissions/options")
def options() -> dict[str, Any]:
    return service.options()


@router.post("/admissions/enquiries/public")
def public_enquiry(body: EnquiryIn, request: Request) -> dict[str, Any]:
    return service.public_enquiry(request, body)


@router.post("/apply/start")
def start(body: StartIn, request: Request) -> dict[str, Any]:
    return service.start(request, body)


@router.post("/apply/code")
def request_code(body: PhoneIn, request: Request) -> dict[str, Any]:
    assert body.phone
    return service.request_code(request, body.phone)


@router.post("/apply/verify")
def verify_code(body: CodeIn, request: Request, response: Response) -> dict[str, Any]:
    assert body.phone
    return service.verify_code(request, response, body.phone, body.code)


# --- the applicant --------------------------------------------------------------------------


@router.get("/me/application")
def my_application(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.my_application(ctx)


@router.put("/me/application")
def save(body: ApplicationIn, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.save(ctx, body)


@router.post("/me/application/documents")
async def add_document(
    type: DocumentType = Form(...), file: UploadFile = File(...), ctx: AuthContext = ME
) -> dict[str, Any]:
    data = await file.read(MAX_BYTES + 1)
    return service.add_document(ctx, type, file.filename or "document", data)


@router.delete("/me/application/documents/{document_id}")
def remove_document(document_id: str, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.remove_document(ctx, document_id)


@router.post("/me/application/submit")
def submit(request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.submit(ctx, client_ip(request))


@router.post("/me/application/fee", status_code=201)
def start_fee(ctx: AuthContext = ME) -> dict[str, Any]:
    return service.start_fee(ctx)


@router.post("/me/application/fee/{payment_id}/confirm")
def confirm_fee(payment_id: str, body: PaymentConfirm, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.confirm_fee(ctx, payment_id, body.razorpay_payment_id, body.razorpay_signature, client_ip(request))


# --- Admission Cell -------------------------------------------------------------------------


@router.get("/admissions/cycles")
def cycles(ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.list_cycles()


@router.post("/admissions/cycles", status_code=201)
def create_cycle(body: CycleIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create_cycle(ctx, body, client_ip(request))


@router.put("/admissions/cycles/{cycle_id}")
def update_cycle(cycle_id: str, body: CycleUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_cycle(ctx, cycle_id, body, client_ip(request))


@router.get("/admissions/enquiries")
def enquiries(
    status: EnquiryStatus | None = None, q: str | None = Query(None, max_length=60), ctx: AuthContext = READ
) -> list[dict[str, Any]]:
    return service.list_enquiries(status, q)


@router.post("/admissions/enquiries", status_code=201)
def add_enquiry(body: StaffEnquiryIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.add_enquiry(ctx, body)


@router.patch("/admissions/enquiries/{enquiry_id}")
def update_enquiry(enquiry_id: str, body: EnquiryUpdate, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update_enquiry(ctx, enquiry_id, body)


@router.get("/admissions/applications")
def applications(
    cycle_id: str | None = None,
    programme_id: str | None = None,
    status: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=60),
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return service.list_applications(cycle_id=cycle_id, programme_id=programme_id, status=status, q=q)


@router.get("/admissions/applications/{application_id}")
def application(application_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return service.view(service.get_application(application_id), staff=True)


@router.post("/admissions/applications/{application_id}/documents/{document_id}/decide")
def decide_document(
    application_id: str, document_id: str, body: DocumentDecision, ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return service.decide_document(ctx, application_id, document_id, body.approve, body.reason)


@router.post("/admissions/applications/{application_id}/decide")
def decide(application_id: str, body: Decision, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.decide(ctx, application_id, body.action, body.reason, client_ip(request))


@router.post("/admissions/applications/{application_id}/fee")
def fee_at_counter(application_id: str, body: FeeIn, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.fee_at_counter(ctx, application_id, body.mode, body.reference)


@router.get("/admissions/cycles/{cycle_id}/report")
def report(cycle_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return merit.report(cycle_id)


@router.get("/admissions/cycles/{cycle_id}/rounds")
def rounds(cycle_id: str, programme_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return merit.rounds(cycle_id, programme_id)


@router.post("/admissions/cycles/{cycle_id}/rounds")
def make_round(cycle_id: str, body: RoundIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    """dry_run=true shows who would be offered a seat; false publishes the round."""
    return merit.make_round(ctx, cycle_id, body, client_ip(request))


@router.post("/admissions/applications/{application_id}/confirm")
def confirm(application_id: str, body: ConfirmIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return merit.confirm(ctx, application_id, body, client_ip(request))


@router.get("/admissions/applications/{application_id}/refund-quote")
def refund_quote(application_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    a = service.get_application(application_id)
    if a["status"] != "admitted":
        return {"refundable": None}
    return merit.refund_quote(a)


@router.post("/admissions/applications/{application_id}/cancel")
def cancel(application_id: str, body: CancelIn, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return merit.cancel(ctx, application_id, body.reason, client_ip(request))
