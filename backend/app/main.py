import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.modules.helpdesk import admin as helpdesk_admin
from app.modules.helpdesk import router as helpdesk
from app.modules.system import router as system

logging.basicConfig(level=logging.INFO)

API_V1 = "/api/v1"
# Paths used before versioning (the live help desk calls these); kept as aliases, hidden from the docs.
LEGACY_PREFIX = "/api"

ROUTERS: list[APIRouter] = [system.router, helpdesk.router, helpdesk_admin.router]


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
    install_error_handlers(app)

    for router in ROUTERS:
        app.include_router(router, prefix=API_V1)
        app.include_router(router, prefix=LEGACY_PREFIX, include_in_schema=False)
    return app


app = create_app()
