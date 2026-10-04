"""
Receipt PDF (spec §3.4): college letterhead, student, head-wise breakup, amount in words,
payment details, collector and a QR code linking to the public Verify page. The first print is
the ORIGINAL; every later one says DUPLICATE; a cancelled receipt is marked CANCELLED.

Uses fpdf2's built-in Helvetica (no font files to ship), so text is limited to Latin-1;
"Rs." is used instead of the rupee sign.
"""

import io
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import segno
from fpdf import FPDF

from app.core.money import amount_in_words, format_inr

IST = ZoneInfo("Asia/Kolkata")
FOOTER = "This is a computer-generated receipt and needs no signature. Scan the QR code to check that it is genuine."


def _t(text: Any) -> str:
    return str(text or "").encode("latin-1", "replace").decode("latin-1")


def build(receipt: dict[str, Any], college: dict[str, Any], verify_link: str, copy: str) -> bytes:
    pdf = FPDF(format=(148, 210))  # A5 portrait, in mm
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_title(_t(f"Receipt {receipt['number']}"))
    width = pdf.w - 20

    # Letterhead
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(width, 6, _t(college.get("name") or "College"), align="C")
    pdf.set_font("Helvetica", "", 8)
    sub = " | ".join(x for x in (college.get("address"), college.get("phone"), college.get("email")) if x)
    if sub:
        pdf.multi_cell(width, 4, _t(sub), align="C")
    if college.get("university"):
        pdf.multi_cell(width, 4, _t(f"Affiliated to {college['university']}"), align="C")
    pdf.ln(1)
    pdf.set_draw_color(20, 33, 61)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(width / 2, 6, "FEE RECEIPT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(176, 46, 46) if copy != "ORIGINAL" else pdf.set_text_color(20, 33, 61)
    pdf.cell(width / 2, 6, _t(copy), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    collected = (
        receipt["collected_at"].astimezone(IST)
        if isinstance(receipt["collected_at"], datetime)
        else receipt["collected_at"]
    )
    rows = [
        ("Receipt no.", receipt["number"], "Date", collected.strftime("%d %b %Y, %I:%M %p")),
        ("Student", receipt["student"]["name"], "PRN", receipt["student"]["prn"]),
        ("Class", receipt["student"]["class"], "Academic year", receipt["academic_year"]),
    ]
    pdf.set_font("Helvetica", "", 8.5)
    for a, b, c, d in rows:
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(22, 5.5, _t(a))
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(width / 2 - 22, 5.5, _t(b))
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(22, 5.5, _t(c))
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(width / 2 - 22, 5.5, _t(d), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Head-wise breakup
    pdf.set_fill_color(240, 236, 228)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(width - 35, 6, "Particulars", border=1, fill=True)
    pdf.cell(35, 6, "Amount", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8.5)
    for ln in receipt["lines"]:
        pdf.cell(width - 35, 6, _t(ln["name"]), border=1)
        pdf.cell(35, 6, _t(format_inr(ln["amount"])), border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(width - 35, 7, "Total received", border=1)
    pdf.cell(35, 7, _t(format_inr(receipt["amount"])), border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(width, 5, _t(amount_in_words(receipt["amount"])))
    pdf.ln(1)

    # Payment details
    pdf.set_font("Helvetica", "", 8)
    mode = {
        "cash": "Cash",
        "upi": "UPI",
        "card": "Card",
        "cheque": "Cheque",
        "dd": "Demand draft",
        "bank_transfer": "Bank transfer",
    }
    details = [f"Paid by {mode.get(receipt['mode'], receipt['mode'])}"]
    if receipt.get("reference"):
        details.append(f"Ref. {receipt['reference']}")
    if receipt.get("bank"):
        details.append(receipt["bank"])
    if receipt.get("instrument_date"):
        details.append(f"dated {receipt['instrument_date']}")
    pdf.multi_cell(width - 34, 4.5, _t(", ".join(details)))
    if receipt["mode"] in {"cheque", "dd"}:
        pdf.multi_cell(width - 34, 4.5, "Subject to realisation of the cheque/DD.")
    pdf.multi_cell(width - 34, 4.5, _t(f"Received by {receipt['collector_name']}"))
    if receipt.get("note"):
        pdf.multi_cell(width - 34, 4.5, _t(f"Note: {receipt['note']}"))

    # QR verify link, bottom right
    qr_png = io.BytesIO()
    segno.make(verify_link, error="m").save(qr_png, kind="png", scale=4, border=1)
    qr_png.seek(0)
    qr_y = pdf.h - 52
    pdf.image(qr_png, x=pdf.w - 10 - 30, y=qr_y, w=30, h=30)
    pdf.set_xy(pdf.w - 10 - 44, qr_y + 30.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.multi_cell(44, 3, _t(f"Scan or visit {verify_link}"), align="R")

    pdf.set_xy(10, pdf.h - 22)
    pdf.set_font("Helvetica", "", 7)
    pdf.multi_cell(
        width - 46,
        3.5,
        FOOTER,
    )

    if receipt["status"] == "cancelled":
        with pdf.rotation(30, x=pdf.w / 2, y=pdf.h / 2):
            pdf.set_font("Helvetica", "B", 48)
            pdf.set_text_color(200, 60, 60)
            pdf.set_xy(0, pdf.h / 2 - 10)
            pdf.cell(pdf.w, 20, "CANCELLED", align="C")
        pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())
