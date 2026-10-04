"""
Fee statement PDF (spec R13 "Fees"): every entry of a student's fee account for a year with a
running balance, for scholarship offices, banks (education loans) and the student's records.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.core.money import format_inr
from app.modules.fees.receipt_pdf import _t

IST = ZoneInfo("Asia/Kolkata")


def build(student: dict[str, Any], year_name: str, account: dict[str, Any], college: dict[str, Any]) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_title(_t(f"Fee statement {student['prn']} {year_name}"))
    w = pdf.w - 30

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(w, 7, _t(college.get("name") or "College"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    sub = " | ".join(x for x in (college.get("address"), college.get("phone"), college.get("email")) if x)
    if sub:
        pdf.multi_cell(w, 5, _t(sub), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(20, 33, 61)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(w, 7, _t(f"Fee statement {year_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        w, 6, _t(f"{student['name']}  |  PRN {student['prn']}  |  {student['class']}"), new_x="LMARGIN", new_y="NEXT"
    )
    pdf.cell(
        w, 6, _t(f"Generated on {datetime.now(IST).strftime('%d %b %Y, %I:%M %p')}"), new_x="LMARGIN", new_y="NEXT"
    )
    pdf.ln(3)

    cols = [(24, "Date"), (w - 24 - 30 * 3, "Particulars"), (30, "Charged"), (30, "Credited"), (30, "Balance")]
    pdf.set_fill_color(240, 236, 228)
    pdf.set_font("Helvetica", "B", 9)
    for width, header in cols:
        pdf.cell(
            width, 7, header, border=1, fill=True, align="R" if header in {"Charged", "Credited", "Balance"} else "L"
        )
    pdf.ln()
    pdf.set_font("Helvetica", "", 8.5)
    running = 0
    for e in account["entries"]:
        running += e["amount"]
        text = (
            e["label"]
            + (f" {e['receipt_number']}" if e.get("receipt_number") else "")
            + (" (cancelled)" if e.get("reversed") else "")
        )
        if e.get("reason") and e["type"] not in {"payment"}:
            text += f" - {e['reason']}"
        date = datetime.fromisoformat(e["at"]).astimezone(IST).strftime("%d-%m-%Y")
        values = [
            date,
            text[:70],
            format_inr(e["amount"]) if e["amount"] > 0 else "",
            format_inr(-e["amount"]) if e["amount"] < 0 else "",
            format_inr(running),
        ]
        for (width, header), value in zip(cols, values, strict=True):
            pdf.cell(
                width, 6.5, _t(value), border=1, align="R" if header in {"Charged", "Credited", "Balance"} else "L"
            )
        pdf.ln()
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    totals = [
        ("Total fee and charges", account["demand"] + account["charges"]),
        ("Paid", account["paid"]),
        ("Concessions", account["concessions"]),
        ("Scholarships", account["scholarships"]),
        ("Balance due" if account["balance"] >= 0 else "In credit", abs(account["balance"])),
    ]
    for label, value in totals:
        pdf.cell(w - 40, 6.5, _t(label), align="R")
        pdf.cell(40, 6.5, _t(format_inr(value)), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(
        w,
        4,
        "Computer-generated statement from CollegeConnect. Each receipt listed can be checked on the college's "
        "Verify page using the QR code printed on it.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())
