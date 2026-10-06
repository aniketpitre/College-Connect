from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthContext, signed_in
from app.core.requestinfo import client_ip
from app.modules.exams import hall_ticket_pdf, service
from app.modules.exams.schemas import SessionIn, SessionUpdate, VerifyIn
from app.modules.setup import service as setup
from app.modules.timetable.service import oid

router = APIRouter(tags=["exams"])
ME = Depends(signed_in)


def _pdf(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.get("/exams/sessions")
def sessions(ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.list_sessions(ctx)


@router.post("/exams/sessions", status_code=201)
def create(body: SessionIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.create_session(ctx, body, client_ip(request))


@router.patch("/exams/sessions/{session_id}")
def update(session_id: str, body: SessionUpdate, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.update_session(ctx, session_id, body, client_ip(request))


@router.get("/exams/sessions/{session_id}/forms")
def forms(session_id: str, ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.forms(ctx, session_id)


@router.post("/exams/sessions/{session_id}/forms/{student_id}/verify")
def verify(session_id: str, student_id: str, body: VerifyIn, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.verify(ctx, session_id, student_id, body.approve, body.reason, client_ip(request))


@router.post("/exams/sessions/{session_id}/verify-eligible")
def verify_eligible(session_id: str, request: Request, ctx: AuthContext = ME) -> dict[str, int]:
    return service.verify_eligible(ctx, session_id, client_ip(request))


@router.post("/exams/sessions/{session_id}/seat-numbers")
def seats(session_id: str, request: Request, ctx: AuthContext = ME) -> dict[str, int]:
    return service.assign_seats(ctx, session_id, client_ip(request))


@router.get("/exams/sessions/{session_id}/export")
def export(session_id: str, ctx: AuthContext = ME) -> Response:
    filename, data = service.export_csv(ctx, session_id)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.get("/exams/sessions/{session_id}/hall-tickets/{student_id}.pdf")
def hall_ticket(session_id: str, student_id: str, ctx: AuthContext = ME) -> Response:
    service._require_manage(ctx)
    s, form, student = service.hall_ticket_data(session_id, oid(student_id, "Student"))
    return _pdf(hall_ticket_pdf.build(s, form, student, setup.institution()), f"hall-ticket-{student['prn']}.pdf")


@router.get("/me/exams")
def my_exams(ctx: AuthContext = ME) -> list[dict[str, Any]]:
    return service.my_exams(ctx)


@router.post("/me/exams/{session_id}/form")
def submit_form(session_id: str, request: Request, ctx: AuthContext = ME) -> dict[str, Any]:
    return service.submit_form(ctx, session_id, client_ip(request))


@router.get("/me/exams/{session_id}/hall-ticket.pdf")
def my_hall_ticket(session_id: str, ctx: AuthContext = ME) -> Response:
    s, form, student = service.my_hall_ticket(ctx, session_id)
    return _pdf(hall_ticket_pdf.build(s, form, student, setup.institution()), f"hall-ticket-{student['prn']}.pdf")
