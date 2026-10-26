"""Renders the Reporter's already-computed numbers + narrative text into a PDF.
Pure formatting — no math happens here; every figure printed was already in the
reports.py dataclass or ai/reporter.py narrative object passed in.
"""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ai.reporter import BusinessNarrative, GroupNarrative, NonprofitNarrative
from reports import BusinessReportData, GroupReportData, NonprofitReportData

styles = getSampleStyleSheet()
H1 = styles["Heading1"]
H2 = styles["Heading2"]
BODY = styles["BodyText"]


def _pending_table(pending: list[dict]) -> list:
    flowables = [Paragraph("Still Waiting for Approval", H2)]
    if not pending:
        flowables.append(Paragraph("Nothing is currently pending.", BODY))
        return flowables
    rows = [["Pot", "Merchant", "Amount", "Date"]]
    rows += [[p["pot_name"], p["merchant"], f"${p['amount']:,.2f}", p["date"]] for p in pending]
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    flowables.append(table)
    return flowables


def _build(workspace_name: str, title: str, body: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    story = [Paragraph(workspace_name, H1), Paragraph(f"{title} — {date.today().strftime('%B %Y')}", styles["Heading3"]), Spacer(1, 0.2 * inch)]
    story += body
    doc.build(story)
    return buffer.getvalue()


def build_nonprofit_pdf(workspace_name: str, data: NonprofitReportData, narrative: NonprofitNarrative, pending: list[dict]) -> bytes:
    body = [Paragraph("Board Summary", H2), Paragraph(narrative.board_summary, BODY), Spacer(1, 0.15 * inch)]

    stories_by_pot = {s.pot_name: s.story for s in narrative.grant_stories}
    body.append(Paragraph("Grant Reports", H2))
    for g in data.grants:
        body.append(Paragraph(f"<b>{g.pot_name}</b> (funder: {g.grantor or 'unspecified'})", BODY))
        body.append(Paragraph(f"Spent ${g.spent:,.2f} of ${g.budget:,.2f} ({g.pct_used:.1f}%) — ${g.remaining:,.2f} remaining.", BODY))
        if g.end_date:
            body.append(Paragraph(f"Grant period ends {g.end_date.strftime('%m/%d/%Y')}.", BODY))
        if g.report_deadlines:
            deadlines = "; ".join(f"{d['description']} by {d['date']}" for d in g.report_deadlines)
            body.append(Paragraph(f"Report deadlines: {deadlines}", BODY))
        story_text = stories_by_pot.get(g.pot_name)
        if story_text:
            body.append(Paragraph(story_text, BODY))
        body.append(Spacer(1, 0.1 * inch))

    body.append(Spacer(1, 0.1 * inch))
    body.append(Paragraph("Spending by IRS Form 990 Category", H2))
    rows = [["Category", "Amount"]] + [[k, f"${v:,.2f}"] for k, v in data.bucket_totals.items()]
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    body.append(table)
    body.append(Spacer(1, 0.2 * inch))
    body += _pending_table(pending)
    return _build(workspace_name, "Nonprofit Report", body)


def build_group_pdf(workspace_name: str, data: GroupReportData, narrative: GroupNarrative, pending: list[dict]) -> bytes:
    body = [Paragraph(narrative.intro, BODY), Spacer(1, 0.15 * inch)]

    body.append(Paragraph("Wins", H2))
    body.append(Paragraph(" ".join(data.wins) if data.wins else "No big wins to report this month.", BODY))
    body.append(Paragraph("Overspending", H2))
    body.append(Paragraph(" ".join(data.overspending) if data.overspending else "Nothing went over budget this month.", BODY))

    if data.goal_progress:
        body.append(Paragraph("Goal Progress", H2))
        rows = [["Goal", "Saved", "Target", "% There"]]
        rows += [[g["pot_name"], f"${g['current']:,.2f}", f"${g['target']:,.2f}", f"{g['pct']:.1f}%"] for g in data.goal_progress]
        table = Table(rows, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))]))
        body.append(table)

    body.append(Spacer(1, 0.1 * inch))
    body.append(Paragraph("Who Owes Whom", H2))
    if data.transfers:
        for t in data.transfers:
            body.append(Paragraph(f"{t['from']} owes {t['to']}: ${t['amount']:,.2f}", BODY))
    else:
        body.append(Paragraph("Everyone's settled up.", BODY))

    body.append(Spacer(1, 0.15 * inch))
    body.append(Paragraph("Let's Talk About It", H2))
    body.append(ListFlowable([ListItem(Paragraph(q, BODY)) for q in narrative.discussion_questions], bulletType="bullet"))

    body.append(Spacer(1, 0.2 * inch))
    body += _pending_table(pending)
    return _build(workspace_name, "Monthly Money Check-In", body)


def build_business_pdf(workspace_name: str, data: BusinessReportData, narrative: BusinessNarrative, pending: list[dict]) -> bytes:
    body = [
        Paragraph("Cash Flow Summary", H2),
        Paragraph(f"Sales: ${data.sales:,.2f} &nbsp;&nbsp; Costs: ${data.costs:,.2f} &nbsp;&nbsp; Net: ${data.net:,.2f}", BODY),
        Paragraph(narrative.cash_flow_summary, BODY),
        Spacer(1, 0.15 * inch),
    ]

    if data.reserve_status:
        body.append(Paragraph("Reserve Status", H2))
        for r in data.reserve_status:
            target_text = f" of ${r['target']:,.2f} target" if r["target"] else ""
            body.append(Paragraph(f"{r['pot_name']}: ${r['current']:,.2f}{target_text}", BODY))

    if data.payroll_status:
        body.append(Paragraph("Payroll Coverage", H2))
        ps = data.payroll_status
        status_text = "on track" if ps["covered"] else f"short by ${ps['shortfall']:,.2f}"
        body.append(Paragraph(f"{ps['pot_name']}: ${ps['current_balance']:,.2f} available, next run ~${ps['expected_amount']:,.2f} — {status_text}.", BODY))

    body.append(Spacer(1, 0.1 * inch))
    body.append(Paragraph("Runway", H2))
    runway_text = f"About {data.runway_months} months of cash at the current burn rate." if data.runway_months is not None else "Not enough history to estimate runway yet."
    body.append(Paragraph(runway_text, BODY))

    body.append(Spacer(1, 0.15 * inch))
    body.append(Paragraph("Top 3 Things to Do", H2))
    body.append(ListFlowable([ListItem(Paragraph(a, BODY)) for a in narrative.top_actions], bulletType="bullet"))

    body.append(Spacer(1, 0.2 * inch))
    body += _pending_table(pending)
    return _build(workspace_name, "Business Report", body)
