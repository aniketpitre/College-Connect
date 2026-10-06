"""
What a signed-in parent may call (deny by default).

Parents reuse the student's `/me/*` pages for the child picked with the `X-Child` header. Each
allowed route names the area the student's consent controls (None: always shown). Anything not
listed (the student's own profile, documents, exam form, data export, staff pages) is refused,
so a new student endpoint stays closed to parents until it is added here on purpose.
"""

from app.core.errors import AppError

API_V1 = "/api/v1"

ROUTES: dict[tuple[str, str], str | None] = {
    ("GET", "/me/home"): None,
    ("GET", "/me/timetable"): None,
    ("GET", "/me/fees"): "fees",
    ("GET", "/me/fees/statement.pdf"): "fees",
    ("GET", "/me/receipts/{receipt_id}/pdf"): "fees",
    ("POST", "/me/payments"): "fees",  # parents can pay online
    ("POST", "/me/payments/{payment_id}/confirm"): "fees",
    ("GET", "/me/attendance"): "attendance",
    ("GET", "/me/marks"): "results",
    ("GET", "/me/exams"): "results",
    ("GET", "/me/exams/{session_id}/hall-ticket.pdf"): "results",
    ("GET", "/me/results"): "results",
    ("GET", "/me/results/{result_id}.pdf"): "results",
    ("GET", "/me/certificates"): None,
    ("GET", "/me/scholarship-check"): "fees",  # which scholarships the child may qualify for
    ("POST", "/me/certificates"): None,  # a parent may ask for a certificate for their child
    ("GET", "/me/certificates/{request_id}/pdf"): None,
    ("GET", "/notices"): None,
    ("GET", "/notices/{notice_id}"): None,
    ("GET", "/notices/{notice_id}/attachment"): None,
    ("GET", "/files/{file_id}"): None,  # the child's photo only (checked in students.file_for)
    ("POST", "/assistant/ask"): None,
    ("GET", "/me/deadlines"): None,  # deadlines of the child's notices  # documents and the child's class notices
}
# Account pages that aren't about a child.
OWN = {
    ("GET", "/parent/children"),
    ("GET", "/auth/sessions"),
    ("DELETE", "/auth/sessions/{sid}"),
    ("GET", "/auth/login-history"),
    ("PATCH", "/me/preferences"),
    ("GET", "/me/notifications"),
    ("PUT", "/me/notifications"),
}


def area_for(method: str, route_path: str) -> tuple[bool, str | None]:
    """(needs a child, consent area) for an allowed route; raises for anything else."""
    path = route_path.removeprefix(API_V1)
    key = (method, path)
    if key in OWN:
        return False, None
    if key in ROUTES:
        return True, ROUTES[key]
    raise AppError(403, "Parents can't open this page.", "forbidden")
