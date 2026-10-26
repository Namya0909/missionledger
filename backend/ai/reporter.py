"""The Reporter's narrative step. Python (reports.py) has already computed every
number — grant spend/remaining, 990 buckets, wins/overspending/goal progress,
settle-up, sales/costs/runway, and a severity-ranked list of real issues. This
file's only job is turning those given facts into short, readable prose: a story
per grant, a board summary, two no-blame discussion questions, or the top 3
action items (picked from the candidates given, never invented).
"""

import uuid

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy.orm import Session

from ai.core import MAX_AGENT_REQUESTS, NO_REASONING, get_model, log_usage, run_with_retry
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS
from reports import BusinessReportData, GroupReportData, NonprofitReportData


class GrantStoryOut(BaseModel):
    pot_name: str
    story: str = Field(description="2-3 sentences: what this grant funded and how it's tracking.")


class NonprofitNarrative(BaseModel):
    grant_stories: list[GrantStoryOut]
    board_summary: str = Field(description="A short paragraph a board member could read in 30 seconds.")


class GroupNarrative(BaseModel):
    intro: str = Field(description="1-2 friendly sentences summarizing the month, using only the facts given.")
    discussion_questions: list[str] = Field(description="Exactly 2 curious, no-blame questions to talk about together.")


class BusinessNarrative(BaseModel):
    cash_flow_summary: str = Field(description="2-3 sentences on sales, costs, and runway, using only the numbers given.")
    top_actions: list[str] = Field(description="Exactly 3 action items, chosen and phrased from the candidates given.")


async def generate_nonprofit_narrative(db: Session, *, workspace_id: int, user_id: int, data: NonprofitReportData) -> NonprofitNarrative:
    agent = Agent(
        get_model(db),
        output_type=NonprofitNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write short narrative sections for a nonprofit's monthly report. You're given
already-computed numbers for each grant (budget, spent, remaining, pct used) and
overall spending by IRS-990-style bucket. Write one 2-3 sentence story per grant
(what it funded, how it's tracking) and one short board summary paragraph. Only
restate numbers you were given — never compute or invent a new one.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    grants_text = "\n".join(
        f"- {g.pot_name} (funder: {g.grantor or 'unspecified'}): ${g.spent:,.2f} spent of ${g.budget:,.2f} "
        f"({g.pct_used:.1f}%), ${g.remaining:,.2f} remaining, ends {g.end_date.isoformat() if g.end_date else 'n/a'}"
        for g in data.grants
    )
    buckets_text = ", ".join(f"{k}: ${v:,.2f}" for k, v in data.bucket_totals.items())
    prompt = f"Grants:\n{grants_text}\n\nTotal spending by bucket: {buckets_text}\nTotal spent: ${data.total_spent:,.2f}"
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="reporter", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))
    return result.output


async def generate_group_narrative(db: Session, *, workspace_id: int, user_id: int, data: GroupReportData) -> GroupNarrative:
    agent = Agent(
        get_model(db),
        output_type=GroupNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write the friendly intro and discussion prompts for a household/group's monthly
money check-in. You're given already-computed facts: wins, overspending, goal
progress, and who-owes-whom. Write a short, warm intro (no blame, no lecturing) and
exactly 2 curious questions the group could discuss together — frame overspending
as something to understand together, not a failure. Only use the facts given.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    prompt = (
        f"Wins: {data.wins or 'none'}\n"
        f"Overspending: {data.overspending or 'none'}\n"
        f"Goal progress: {data.goal_progress or 'none'}\n"
        f"Balances: {data.balances}\n"
    )
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="reporter", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))
    return result.output


async def generate_business_narrative(db: Session, *, workspace_id: int, user_id: int, data: BusinessReportData) -> BusinessNarrative:
    agent = Agent(
        get_model(db),
        output_type=BusinessNarrative,
        model_settings=NO_REASONING,
        instructions="""
You write a short cash-flow summary and pick the top 3 action items for a small
business's monthly report. You're given already-computed sales, costs, net,
reserve status, payroll coverage, runway in months, and a list of candidate action
items already ranked by severity. Write 2-3 summary sentences using only the given
numbers, then choose and phrase exactly 3 action items FROM the candidates given
(don't invent a new one; if fewer than 3 candidates exist, you may add a generic
but sensible one like "keep an eye on next month's expenses").
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )
    prompt = (
        f"Sales: ${data.sales:,.2f}, Costs: ${data.costs:,.2f}, Net: ${data.net:,.2f}\n"
        f"Reserve status: {data.reserve_status}\n"
        f"Payroll status: {data.payroll_status}\n"
        f"Runway: {data.runway_months} months\n"
        f"Candidate action items (already ranked by severity): {data.action_candidates}"
    )
    result = await run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    log_usage(db, usage=result.usage, purpose="reporter", workspace_id=workspace_id, user_id=user_id, request_id=str(uuid.uuid4()))
    return result.output
