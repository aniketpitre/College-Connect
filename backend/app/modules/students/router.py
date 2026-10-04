from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from app.core.auth import AuthContext, require, signed_in
from app.core.files import MAX_BYTES
from app.core.rbac import P
from app.core.requestinfo import client_ip
from app.modules.students import service
from app.modules.students.schemas import (
    ChangeRequestIn,
    Decision,
    DocumentDecision,
    DocumentType,
    StudentCreate,
    StudentStatus,
    StudentUpdate,
)

router = APIRouter(tags=["students"])
READ = Depends(require(P.STUDENTS_READ))
MANAGE = Depends(require(P.STUDENTS_MANAGE))


async def _read(upload: UploadFile) -> bytes:
    return await upload.read(MAX_BYTES + 1)  # one byte over the limit is enough to reject it


# --- office ---------------------------------------------------------------------------------


@router.get("/students")
def list_students(
    q: str | None = Query(None, max_length=100),
    programme_id: str | None = None,
    year_of_study: int | None = Query(None, ge=1, le=6),
    division_id: str | None = None,
    status: StudentStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    ctx: AuthContext = READ,
) -> dict[str, Any]:
    return service.list_students(
        search=q,
        programme_id=programme_id,
        year_of_study=year_of_study,
        division_id=division_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.post("/students", status_code=201)
def create_student(body: StudentCreate, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.create(ctx, body, client_ip(request))


@router.get("/students/change-requests")
def change_requests(
    status: str | None = Query("pending", pattern="^(pending|approved|rejected)$"),
    student_id: str | None = None,
    ctx: AuthContext = READ,
) -> list[dict[str, Any]]:
    return service.request_queue(status, student_id)


@router.post("/students/change-requests/{request_id}/decide")
def decide_change(request_id: str, body: Decision, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.decide_request(ctx, request_id, body.approve, body.reason, client_ip(request))


@router.get("/students/{student_id}")
def get_student(student_id: str, ctx: AuthContext = READ) -> dict[str, Any]:
    return service.view(service.get_student(service.oid(student_id)))


@router.patch("/students/{student_id}")
def update_student(student_id: str, body: StudentUpdate, request: Request, ctx: AuthContext = MANAGE) -> dict[str, Any]:
    return service.update(ctx, service.oid(student_id), body, client_ip(request))


@router.get("/students/{student_id}/history")
def student_history(student_id: str, ctx: AuthContext = READ) -> list[dict[str, Any]]:
    return service.history(service.oid(student_id))


@router.post("/students/{student_id}/photo")
async def office_photo(
    student_id: str, request: Request, file: UploadFile = File(...), ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    student = service.get_student(service.oid(student_id))
    return service.set_photo(ctx, student, file.filename or "photo", await _read(file), client_ip(request))


@router.post("/students/{student_id}/documents")
async def office_document(
    student_id: str,
    request: Request,
    type: DocumentType = Form(...),
    file: UploadFile = File(...),
    ctx: AuthContext = MANAGE,
) -> dict[str, Any]:
    student = service.get_student(service.oid(student_id))
    data = await _read(file)
    return service.add_document(ctx, student, type, file.filename or type, data, by_office=True, ip=client_ip(request))


@router.post("/students/{student_id}/documents/{document_id}/decide")
def decide_document(
    student_id: str, document_id: str, body: DocumentDecision, request: Request, ctx: AuthContext = MANAGE
) -> dict[str, Any]:
    return service.decide_document(
        ctx, service.oid(student_id), document_id, body.verified, body.reason, client_ip(request)
    )


# --- the student themselves -----------------------------------------------------------------


@router.get("/me/student")
def my_record(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.view(service.my_student(ctx))


@router.get("/me/student/options")
def my_options(ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    """Choices a student needs to ask for a correction (they can't read the college setup)."""
    service.my_student(ctx)
    return service.correction_options()


@router.get("/me/student/change-requests")
def my_change_requests(ctx: AuthContext = Depends(signed_in)) -> list[dict[str, Any]]:
    return service.my_requests(ctx)


@router.post("/me/student/change-requests", status_code=201)
def request_change(body: ChangeRequestIn, request: Request, ctx: AuthContext = Depends(signed_in)) -> dict[str, Any]:
    return service.request_change(ctx, body, client_ip(request))


@router.post("/me/student/photo")
async def my_photo(
    request: Request, file: UploadFile = File(...), ctx: AuthContext = Depends(signed_in)
) -> dict[str, Any]:
    student = service.my_student(ctx)
    return service.set_photo(ctx, student, file.filename or "photo", await _read(file), client_ip(request))


@router.post("/me/student/documents")
async def my_document(
    request: Request,
    type: DocumentType = Form(...),
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(signed_in),
) -> dict[str, Any]:
    student = service.my_student(ctx)
    data = await _read(file)
    return service.add_document(ctx, student, type, file.filename or type, data, by_office=False, ip=client_ip(request))


# --- files ----------------------------------------------------------------------------------


@router.get("/files/{file_id}")
def get_file(file_id: str, ctx: AuthContext = Depends(signed_in)) -> Response:
    doc = service.file_for(ctx, file_id)
    return Response(
        content=bytes(doc["data"]),
        media_type=doc["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{doc["filename"]}"',
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )
