"""Renders the Tax Prep Pack's already-computed numbers + narrative text into a PDF.
Pure formatting, same reportlab pattern as pdf_builder.py — no math happens here.
Every page's body opens with tax_config.TAX_DISCLAIMER in bold, per the explicit
"every page should say" requirement.
"""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tax_config import DONOR_ACK_THRESHOLD, TAX_DISCLAIMER
from tax_prep import BusinessTaxData, GroupTaxData, NonprofitTaxData

styles = getSampleStyleSheet()
H1 = styles["Heading1"]
H2 = styles["Heading2"]
BODY = styles["BodyText"]


def _table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    return table


def _build(workspace_name: str, title: str, body: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    story = [
        Paragraph(workspace_name, H1),
        Paragraph(f"{title} — {date.today().strftime('%B %Y')}", styles["Heading3"]),
        Paragraph(f"<b>{TAX_DISCLAIMER}</b>", BODY),
        Spacer(1, 0.2 * inch),
    ]
    story += body
    doc.build(story)
    return buffer.getvalue()


def build_group_tax_pdf(workspace_name: str, data: GroupTaxData, narrative: list[str]) -> bytes:
    body = [Paragraph(f"Possibly Tax-Relevant Spending — {data.year}", H2)]
    if not data.buckets:
        body.append(Paragraph("Nothing matched a tax-relevant category this year.", BODY))
    for i, bucket in enumerate(data.buckets):
        body.append(Paragraph(f"<b>{bucket.label}</b> — ${bucket.total:,.2f} (possibly relevant — confirm with a tax professional)", BODY))
        if i < len(narrative):
            body.append(Paragraph(narrative[i], BODY))
        rows = [["Date", "Merchant", "Amount", "Receipt on file"]]
        rows += [[it.date.strftime("%m/%d/%Y"), it.merchant, f"${it.amount:,.2f}", "Yes" if it.has_receipt else "No"] for it in bucket.items]
        body.append(_table(rows))
        body.append(Spacer(1, 0.15 * inch))
    body.append(Paragraph(f"<b>Total: ${data.grand_total:,.2f}</b>", BODY))
    return _build(workspace_name, "Tax Prep Pack", body)


def build_nonprofit_tax_pdf(workspace_name: str, data: NonprofitTaxData, filing_summary: str, donor_letters: list[str]) -> bytes:
    body = [
        Paragraph("Form 990 Prep Sheet", H2),
        Paragraph(f"Gross receipts: ${data.gross_receipts:,.2f} &nbsp;&nbsp; Total spending: ${data.total_spending:,.2f} &nbsp;&nbsp; Total assets: ${data.total_assets:,.2f}", BODY),
        Paragraph(f"<b>Likely filing: {data.filing_recommendation}</b> — {data.filing_reason}", BODY),
        Paragraph(filing_summary, BODY),
        Spacer(1, 0.15 * inch),
        Paragraph("Spending by 990 Category", H2),
        _table([["Category", "Amount"]] + [[k, f"${v:,.2f}"] for k, v in data.bucket_totals.items()]),
    ]

    if data.donors:
        body.append(Spacer(1, 0.2 * inch))
        body.append(Paragraph(f"Donor Acknowledgment Letters (${DONOR_ACK_THRESHOLD:,.0f}+ contributions)", H2))
        body.append(Paragraph("Draft only — the treasurer should review each before sending.", BODY))
        for donor, letter_text in zip(data.donors, donor_letters):
            body.append(PageBreak())
            body.append(Paragraph(f"To: {donor.donor_name}", H2))
            for para in letter_text.split("\n\n"):
                body.append(Paragraph(para, BODY))
                body.append(Spacer(1, 0.1 * inch))
    return _build(workspace_name, "Tax Prep Pack", body)


def build_business_tax_pdf(workspace_name: str, data: BusinessTaxData, narrative: str) -> bytes:
    rate_note = " (estimate — confirm your state's current rate)" if data.rate_is_estimate else ""
    body = [
        Paragraph("Sales Tax Worksheet", H2),
        Paragraph(
            f"Taxable sales: ${data.taxable_sales:,.2f} &nbsp;&nbsp; Rate: {data.sales_tax_rate * 100:.2f}%{rate_note} "
            f"&nbsp;&nbsp; Tax owed: ${data.tax_owed:,.2f} &nbsp;&nbsp; Already saved: ${data.already_saved:,.2f}",
            BODY,
        ),
        Paragraph(narrative, BODY),
        Spacer(1, 0.15 * inch),
        Paragraph("Quarterly Estimated Tax", H2),
        Paragraph(f"Next due date: {data.next_estimated_due_date.strftime('%B %d, %Y')} (verify on irs.gov/payments/estimated-taxes).", BODY),
        Spacer(1, 0.15 * inch),
        Paragraph("Contractors Paid $600+ This Year (review for possible 1099-NEC)", H2),
    ]
    if data.contractors:
        body.append(_table([["Merchant", "Total Paid"]] + [[c.merchant, f"${c.total_paid:,.2f}"] for c in data.contractors]))
    else:
        body.append(Paragraph("No single vendor was paid $600 or more this year.", BODY))
    return _build(workspace_name, "Tax Prep Pack", body)
