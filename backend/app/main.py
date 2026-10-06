import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import csrf_guard
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.modules.attendance import router as attendance
from app.modules.auditlog import router as auditlog
from app.modules.auth import router as auth
from app.modules.certificates import router as certificates
from app.modules.dashboard import router as dashboard
from app.modules.exams import router as exams
from app.modules.exports import router as exports
from app.modules.fees import router as fees
from app.modules.helpdesk import admin as helpdesk_admin
from app.modules.helpdesk import router as helpdesk
from app.modules.jobs import router as jobs
from app.modules.marks import router as marks
from app.modules.messaging import router as messaging
from app.modules.notices import router as notices
from app.modules.onboarding import router as onboarding
from app.modules.parents import router as parents
from app.modules.payments import router as payments
from app.modules.portal import router as portal
from app.modules.results import router as results
from app.modules.setup import router as setup
from app.modules.students import router as students
from app.modules.system import router as system
from app.modules.timetable import router as timetable
from app.modules.users import router as users

logging.basicConfig(level=logging.INFO)

API_V1 = "/api/v1"
# Paths used before versioning (the live help desk calls these); kept as aliases, hidden from the docs.
LEGACY_PREFIX = "/api"

ROUTERS: list[APIRouter] = [
    system.router,
    auth.router,
    users.router,
    setup.router,
    students.router,
    onboarding.router,
    fees.router,
    portal.router,
    notices.router,
    auditlog.router,
    exports.router,
    timetable.router,
    attendance.router,
    marks.router,
    exams.router,
    results.router,
    certificates.router,
    jobs.router,
    dashboard.router,
    parents.router,
    payments.router,
    messaging.router,
    helpdesk.router,
    helpdesk_admin.router,
]
# Only these existed before versioning; ERP routes live under /api/v1 alone.
LEGACY_ROUTERS = [system.router, helpdesk.router, helpdesk_admin.router]


async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/") and "/docs" not in request.url.path:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="College ERP with a source-grounded help desk. All endpoints live under /api/v1.",
        version="0.3.0",
        docs_url=f"{API_V1}/docs",
        openapi_url=f"{API_V1}/openapi.json",
    )

    # Local dev: the Vite dev server runs on another port. On Vercel the frontend and API share
    # one origin, so CORS isn't needed; ALLOWED_ORIGINS adds extra origins (comma-separated).
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(csrf_guard)
    app.middleware("http")(security_headers)
    install_error_handlers(app)

    for router in ROUTERS:
        app.include_router(router, prefix=API_V1)
        if any(router is legacy for legacy in LEGACY_ROUTERS):
            app.include_router(router, prefix=LEGACY_PREFIX, include_in_schema=False)
    return app


app = create_app()
