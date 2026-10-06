"""
Which knowledge-base chunks a signed-in person's questions may be answered from.

The same rules as the notice board (`notices.service._visible_query`), applied per chunk:
- public documents: everyone;
- documents for "everyone" (signed-in college members): students, parents, staff;
- notices: students and parents see those for everyone, all students, or their (child's) class;
  staff see those for everyone and staff, and notice publishers and help-desk managers see all;
- applicants only public documents.
A notice counts only between its publish time and the end of its expiry day.
"""

from datetime import UTC, datetime
from typing import Any

from app.core.auth import AuthContext
from app.core.errors import AppError
from app.core.rbac import P
from app.modules.students import service as students
from app.rag.store import Allowed, is_live, public_only


def chunk_filter(ctx: AuthContext) -> Allowed:
    now = datetime.now(UTC)
    kind = ctx.user.get("kind")
    if kind == "applicant":
        return public_only(now)
    if kind in ("student", "parent"):
        try:
            s: dict[str, Any] | None = students.my_student(ctx)  # a parent: the child picked with X-Child
        except AppError:
            s = None
        programme = str(s["programme_id"]) if s and s.get("programme_id") else None
        year = s.get("year_of_study") if s else None
        division = str(s["division_id"]) if s and s.get("division_id") else None

        def learner(c: dict) -> bool:
            a = c.get("audience", {"kind": "public"})
            if a["kind"] in ("public", "everyone", "students"):
                return is_live(c, now)
            if a["kind"] == "class":
                return (
                    programme is not None
                    and a.get("programme_id") == programme
                    and a.get("year_of_study") in (None, year)
                    and a.get("division_id") in (None, division)
                    and is_live(c, now)
                )
            return False

        return learner
    if P.NOTICES_PUBLISH in ctx.permissions or P.KB_MANAGE in ctx.permissions:
        return lambda c: is_live(c, now)
    staff_kinds = ("public", "everyone", "staff")
    return lambda c: c.get("audience", {"kind": "public"})["kind"] in staff_kinds and is_live(c, now)
