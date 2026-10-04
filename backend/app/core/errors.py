"""
One error format for the whole API:

    {"error": {"code": "not_found", "message": "Student not found", "field": "prn"}}

`field` is present only for validation errors. Raise `AppError` from services for
expected failures; FastAPI's HTTPException and validation errors are converted too.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    503: "unavailable",
}


class AppError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None, field: str | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code or STATUS_CODES.get(status, "error")
        self.field = field


def error_body(code: str, message: str, field: str | None = None) -> dict:
    error: dict[str, str] = {"code": code, "message": message}
    if field:
        error["field"] = field
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.field), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, "error")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
        return JSONResponse(
            error_body("validation_error", first.get("msg", "Invalid request"), ".".join(loc) or None),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(error_body("internal_error", "Something went wrong. Please try again."), status_code=500)
