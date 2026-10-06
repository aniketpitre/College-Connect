"""Statement of result PDF (not the university's marksheet), made on demand."""

from typing import Any

from fpdf import FPDF

from app.modules.fees.receipt_pdf import _t


def build(
    result: dict[str, Any],
    session: dict[str, Any],
    student: dict[str, Any],
    college: dict[str, Any],
    cgpa: float | None,
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_title(_t(f"Result {student['prn']}"))
    w = pdf.w - 30
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(w, 7, _t(college.get("name") or "College"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    if college.get("university"):
        pdf.multi_cell(w, 5, _t(f"Affiliated to {college['university']}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(20, 33, 61)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(w, 7, "STATEMENT OF RESULT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(w, 6, _t(session["name"]), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(w, 6, _t(f"{student['name']}  |  PRN {student['prn']}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    cols = [
        (24, "Code"),
        (w - 24 - 18 * 5, "Paper"),
        (18, "Int"),
        (18, "Ext"),
        (18, "Total"),
        (18, "Grade"),
        (18, "Credits"),
    ]
    pdf.set_fill_color(240, 236, 228)
    pdf.set_font("Helvetica", "B", 9)
    for width, header in cols:
        pdf.cell(width, 7, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    fmt = lambda v: "-" if v is None else f"{v:g}"  # noqa: E731
    for s in result["subjects"]:
        pdf.cell(24, 7, _t(s["code"]), border=1)
        pdf.cell(w - 24 - 18 * 5, 7, _t(s["name"])[:60], border=1)
        pdf.cell(18, 7, fmt(s["internal"]), border=1, align="R")
        pdf.cell(18, 7, fmt(s["external"]), border=1, align="R")
        pdf.cell(18, 7, fmt(s["total"]), border=1, align="R")
        pdf.cell(18, 7, _t(s["grade"]), border=1, align="C")
        pdf.cell(18, 7, fmt(s["credits"]), border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    outcome = {"pass": "PASS", "atkt": "ATKT (backlog to clear)", "absent": "ABSENT"}[result["outcome"]]
    sg = "-" if result["sgpa"] is None else f"{result['sgpa']:.2f}"
    cg = "-" if cgpa is None else f"{cgpa:.2f}"
    pdf.cell(w, 7, _t(f"SGPA {sg}   |   CGPA {cg}   |   Result: {outcome}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.multi_cell(
        w,
        5,
        _t("This statement is for information only. The university's marksheet is the official record."),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())
