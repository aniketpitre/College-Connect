"""Certificate PDFs, made on demand from the snapshot taken at issue time (nothing stored)."""

import io
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

import segno
from fpdf import FPDF

from app.core.money import format_inr
from app.modules.certificates.service import SIGNER_LABEL, TYPES
from app.modules.fees.receipt_pdf import _t

IST = ZoneInfo("Asia/Kolkata")


def _d(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d %B %Y") if iso else "-"


def body(kind: str, d: dict[str, Any], college: str) -> list[str]:
    who = f"{d['name']} (PRN {d['prn']})"
    if kind == "bonafide":
        return [
            f"This is to certify that {who} is a bonafide student of {college}, studying in {d['class']} "
            f"({d.get('programme') or ''}) in the academic year {d.get('academic_year') or '-'}.",
            f"This certificate is issued at the student's request for: {d['purpose']}.",
        ]
    if kind == "character":
        return [
            f"This is to certify that {who} is a student of {college}, studying in {d['class']}.",
            "To the best of our knowledge, the student's conduct and character during this period have been good.",
            f"Issued for: {d['purpose']}.",
        ]
    if kind == "fee_paid":
        return [
            f"This is to certify that {who}, studying in {d['class']}, has paid "
            f"{format_inr(d.get('fees_paid', 0)).replace(chr(8377), 'Rs. ')} as fees for the academic year "
            f"{d.get('academic_year') or '-'}."
            + (
                f" Fees still due: {format_inr(d['fees_due']).replace(chr(8377), 'Rs. ')}."
                if d.get("fees_due")
                else " No fees are due."
            ),
            f"Issued for: {d['purpose']}.",
        ]
    if kind == "tc":
        return [
            f"This is to certify that {who} was a student of {college}.",
            f"Programme: {d.get('programme') or '-'}.   Class last attended: {d['class']}.",
            f"Date of birth: {_d(d.get('dob'))}.   Date of admission: {_d(d.get('admission_date'))}.",
            f"Reason for leaving: {d.get('reason_for_leaving') or '-'}.",
            "Conduct: Good.   Dues to the college: Nil.",
            "The student's name has been removed from the rolls of the college.",
        ]
    if kind == "migration":
        return [
            f"This is to certify that {who}, a student of {college} in {d['class']}, has no dues to the college.",
            "The college has no objection to the student migrating to another university. "
            f"Reason: {d.get('reason_for_leaving') or '-'}.",
        ]
    return [
        f"This is to certify that {who} is a student of {college}, studying in {d['class']}.",
        f"The college has no objection to the student doing an internship at {d.get('organisation') or '-'} "
        f"from {_d(d.get('from_date'))} to {_d(d.get('to_date'))}.",
        f"Purpose: {d['purpose']}.",
    ]


def build(cert: dict[str, Any], college: dict[str, Any], verify_link: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_title(_t(f"{TYPES[cert['type']]['name']} {cert['number']}"))
    w = pdf.w - 40
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(w, 8, _t(college.get("name") or "College"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    sub = " | ".join(x for x in (college.get("address"), college.get("phone"), college.get("email")) if x)
    if sub:
        pdf.multi_cell(w, 5, _t(sub), align="C", new_x="LMARGIN", new_y="NEXT")
    if college.get("university"):
        pdf.multi_cell(w, 5, _t(f"Affiliated to {college['university']}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(20, 33, 61)
    pdf.set_line_width(0.6)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    issued = cert["issued_at"].astimezone(IST).strftime("%d %B %Y")
    pdf.cell(w / 2, 6, _t(f"No. {cert['number']}"))
    pdf.cell(w / 2, 6, _t(f"Date: {issued}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(w, 9, _t(TYPES[cert["type"]]["name"].upper()), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11.5)
    for para in body(cert["type"], cert["data"], college.get("name") or "this college"):
        pdf.multi_cell(w, 7, _t(para), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    pdf.ln(24)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(w, 6, _t(SIGNER_LABEL[TYPES[cert["type"]]["signer"]]), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(w, 5, _t(college.get("name") or ""), align="R", new_x="LMARGIN", new_y="NEXT")

    qr = io.BytesIO()
    segno.make(verify_link, error="m").save(qr, kind="png", scale=4, border=1)
    qr.seek(0)
    y = pdf.h - 52
    pdf.image(qr, x=20, y=y, w=30, h=30)
    pdf.set_xy(54, y + 6)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(
        w - 34, 4.5, _t(f"Scan to check this certificate, or open {verify_link}"), new_x="LMARGIN", new_y="NEXT"
    )
    return bytes(pdf.output())
