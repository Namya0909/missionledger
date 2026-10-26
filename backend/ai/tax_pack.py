"""Tax Prep Pack narrative step. tax_prep.py has already computed every number
(bucket totals, 990 filing recommendation, sales tax owed, due dates, 1099
candidates) — this file's only job is turning those given facts into short,
readable prose, same pattern as ai/reporter.py.

One deliberate difference from ai/reporter.py: a report has no partial version, so
its narrative failure correctly fails the whole request. The Tax Prep Pack's real
value is the organized Python numbers — AI only adds explanatory sentences on top —
so routers/tax_pack.py wraps each of these calls in a try/except and falls back to a
plain built-in sentence on failure (same graceful-degrade pattern routers/attention.py
already uses), rather than failing the whole PDF/CSV.

For the nonprofit donor thank-you letters: the IRS-required disclosure sentence (IRS
Pub. 1771 — whether any goods/services were provided in exchange) is a fixed Python
template, never AI-generated text, since getting that sentence wrong is a compliance
problem, not a prose-quality one. The AI only writes the warm opening/closing
paragraphs around it.
"""

import uuid

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy.orm import Session

from ai.core import MAX_AGENT_REQUESTS, NO_REASONING, get_model, log_usage, run_with_retry
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS
from tax_prep import BusinessTaxData, GroupTaxData, NonprofitTaxData

# IRS Publication 1771's required disclosure for a cash donation where nothing was
# given in exchange — this app has no way to know if something WAS given (a dinner,
# a gift), so every letter states the no-goods-or-services version and the treasurer
# is told explicitly to edit this line by hand for any donation where that's untrue.
REQUIRED_DONOR_DISCLOSURE = (
    "No goods or services were provided in exchange for this contribution, other than "
    "intangible religious benefits, if applicable."
)


class GroupTaxNarrative(BaseModel):
    bucket_sentences: list[str] = Field(
        description="One short sentence per bucket given, in the same order, restating its total and category."
    )


class DonorLetterParts(BaseModel):
    opening: str = Field(description="1 warm sentence thanking the donor by name for their specific contribution.")
    closing: str = Field(description="1 short closing sentence, e.g. inviting them to reach out with questions.")


class NonprofitTaxNarrative(BaseModel):
    filing_summary: str = Field(description="2-3 sentences explaining which 990 variant applies and why, using only the given numbers.")
    donor_letters: list[DonorLetterParts] = Field(description="One opening/closing pair per donor given, same order.")


class BusinessTaxNarrative(BaseModel):
    summary: str = Field(description="2-3 sentences on the sales tax worksheet, due date, and any 1099 candidates, using only the given numbers.")


async def generate_group_tax_narrative(db: Session, *, workspace_id: int, user_id: int, data: GroupTaxData) -> GroupTaxNarrative:
    agent = Agent(
        get_model(db),
        output_type=GroupTaxNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write one short, matter-of-fact sentence per spending bucket in a household's
year-end "possibly tax-relevant" summary (e.g. charitable donations, medical,
childcare, student loan interest, home office). You're given each bucket's label and
total — restate it plainly (e.g. "$640 in medical expenses were logged this year —
bring these receipts to your tax preparer.") Never claim something IS deductible,
only that it's organized here for review. Only use the numbers given.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    prompt = "Buckets:\n" + "\n".join(f"- {b.label}: ${b.total:,.2f} ({len(b.items)} item(s))" for b in data.buckets)
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="tax_pack", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))
    return result.output


async def generate_nonprofit_tax_narrative(
    db: Session, *, workspace_id: int, user_id: int, org_name: str, data: NonprofitTaxData
) -> tuple[str, list[str]]:
    """Returns (filing_summary, donor_letters) — donor_letters are fully assembled
    strings (Python facts + fixed legal disclosure + AI's opening/closing prose)."""
    agent = Agent(
        get_model(db),
        output_type=NonprofitTaxNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write a short filing-recommendation summary and donor thank-you letter framing
for a nonprofit's Tax Prep Pack. You're given already-computed facts: gross receipts,
total spending, which Form 990 variant likely applies and why, and a list of donors
(name, amount, date) each needing a thank-you letter. Write 2-3 plain sentences
explaining the filing recommendation using only the numbers given — never invent a
number or claim a filing requirement that wasn't given to you. For each donor, write
exactly one warm opening sentence (using their name and the specific amount/date) and
one short closing sentence — you do NOT write the required legal disclosure sentence;
that's inserted separately. Never suggest or imply a deduction amount a donor could
claim — that's the donor's own tax preparer's call.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    donors_text = "\n".join(f"- {d.donor_name}: ${d.amount:,.2f} on {d.date.isoformat()}" for d in data.donors)
    prompt = (
        f"Gross receipts: ${data.gross_receipts:,.2f}\nTotal spending: ${data.total_spending:,.2f}\n"
        f"Total assets: ${data.total_assets:,.2f}\nFiling recommendation: {data.filing_recommendation} "
        f"({data.filing_reason})\nDonors needing a thank-you letter:\n{donors_text or 'none'}"
    )
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="tax_pack", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))

    letters = []
    for donor, parts in zip(data.donors, result.output.donor_letters):
        letters.append(
            f"{parts.opening}\n\n"
            f"Thank you for your generous gift of ${donor.amount:,.2f} to {org_name}, received on "
            f"{donor.date.strftime('%B %d, %Y')}. {REQUIRED_DONOR_DISCLOSURE}\n\n"
            f"{parts.closing}"
        )
    return result.output.filing_summary, letters


async def generate_business_tax_narrative(db: Session, *, workspace_id: int, user_id: int, data: BusinessTaxData) -> str:
    agent = Agent(
        get_model(db),
        output_type=BusinessTaxNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write a short summary for a small business's Tax Prep Pack: sales-tax worksheet,
next estimated-tax due date, and any contractors who may need a 1099-NEC. You're given
already-computed facts — only restate them plainly in 2-3 sentences, never invent a
new number, and never tell them which contractors definitely need a 1099 (say
"review these" since that depends on facts this app doesn't have, like whether each
payee is incorporated).
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    contractors_text = ", ".join(f"{c.merchant} (${c.total_paid:,.2f})" for c in data.contractors) or "none"
    prompt = (
        f"Taxable sales: ${data.taxable_sales:,.2f}, rate: {data.sales_tax_rate * 100:.2f}%"
        f"{' (estimate)' if data.rate_is_estimate else ''}, tax owed: ${data.tax_owed:,.2f}, "
        f"already saved: ${data.already_saved:,.2f}\n"
        f"Next estimated-tax due date: {data.next_estimated_due_date.isoformat()}\n"
        f"Contractors paid $600+ this year: {contractors_text}"
    )
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="tax_pack", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))
    return result.output.summary
