"""
What a signed-in admission applicant may call (deny by default): their own application,
its documents and fee, and their account basics. Nothing else in the ERP is reachable.
"""

from app.core.errors import AppError

API_V1 = "/api/v1"

ALLOWED = {
    ("GET", "/me/application"),
    ("PUT", "/me/application"),
    ("POST", "/me/application/documents"),
    ("DELETE", "/me/application/documents/{document_id}"),
    ("POST", "/me/application/submit"),
    ("POST", "/me/application/fee"),
    ("POST", "/me/application/fee/{payment_id}/confirm"),
    ("GET", "/files/{file_id}"),  # their own uploads only (students.file_for)
    ("GET", "/admissions/options"),
    ("PATCH", "/me/preferences"),
    ("GET", "/me/notifications"),
    ("PUT", "/me/notifications"),
}


def check(method: str, route_path: str) -> None:
    if (method, route_path.removeprefix(API_V1)) not in ALLOWED:
        raise AppError(403, "Applicants can only open their application.", "forbidden")
