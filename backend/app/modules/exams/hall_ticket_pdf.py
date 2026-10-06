"""Hall ticket PDF, made on demand (nothing is stored)."""

from datetime import date
from typing import Any

from fpdf import FPDF

from app.core.db import get_db
from app.modules.fees.receipt_pdf import _t
from app.modules.timetable import service as timetable


def build(session: dict[str, Any], form: dict[str, Any], student: dict[str, Any], college: dict[str, Any]) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_title(_t(f"Hall ticket {student['prn']}"))
    w = pdf.w - 30

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(w, 7, _t(college.get("name") or "College"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    sub = " | ".join(x for x in (college.get("university"), college.get("address")) if x)
    if sub:
        pdf.multi_cell(w, 5, _t(sub), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(20, 33, 61)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(w, 8, "HALL TICKET", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(w, 6, _t(session["name"]), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    division = get_db().divisions.find_one({"_id": student.get("division_id")})
    rows = [
        ("Seat number", form["seat_no"]),
        ("Name", student["name"]),
        ("PRN", student["prn"]),
        ("Class", timetable._division_label(division) if division else ""),
    ]
    pdf.set_font("Helvetica", "", 10)
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 7, _t(label), border=1)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(w - 40, 7, _t(value), border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    taking = {x["subject_id"] for x in form["subjects"]}
    papers = sorted(
        (p for p in session.get("papers", []) if p["subject_id"] in taking), key=lambda p: (p["date"], p["start"])
    )
    names = {x["subject_id"]: x for x in form["subjects"]}
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 236, 228)
    cols = [(30, "Date"), (30, "Time"), (w - 60, "Paper")]
    for width, header in cols:
        pdf.cell(width, 7, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9.5)
    if not papers:
        pdf.cell(
            w,
            7,
            _t("The paper timetable will be announced on the notice board."),
            border=1,
            new_x="LMARGIN",
            new_y="NEXT",
        )
    for p in papers:
        x = names[p["subject_id"]]
        pdf.cell(30, 7, date.fromisoformat(p["date"]).strftime("%d %b %Y"), border=1)
        pdf.cell(30, 7, f"{p['start']}-{p['end']}", border=1)
        label = f"{x['code']} {x['name']}" + (" (backlog)" if x.get("backlog") else "")
        pdf.cell(w - 60, 7, _t(label)[:80], border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    for line in (
        "Bring this hall ticket and your college identity card to every paper.",
        "Reach the examination hall 30 minutes before the paper starts.",
        "Mobile phones and smart watches are not allowed in the examination hall.",
    ):
        pdf.multi_cell(w, 5, _t(f"- {line}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)
    pdf.cell(w / 2, 6, "Student's signature")
    pdf.cell(w / 2, 6, "Controller of Examinations", align="R", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
