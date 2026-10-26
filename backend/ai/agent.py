"""The transaction-review agent: categorizes a new transaction and checks it
against its pot's rules (budget, monthly limit, allowed/disallowed categories,
grant window) before it goes to a human for approval.
"""

import uuid

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from sqlalchemy.orm import Session

import models
from ai.core import MAX_AGENT_REQUESTS, NO_REASONING, get_model, log_usage
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS, wrap_untrusted


class TransactionReview(BaseModel):
    """Structured output: a suggested category and any policy warnings."""

    category: str = Field(description="A short, human-friendly spending category.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Plain-language policy warnings, empty if the transaction looks fine.",
    )
    reasoning: str = Field(description="One short sentence explaining the warnings, or why there are none.")


def build_transaction_review_agent(db: Session) -> Agent[None, TransactionReview]:
    return Agent(
        get_model(db),
        output_type=TransactionReview,
        model_settings=NO_REASONING,
        instructions="""
You review a single financial transaction against the spending rules of the "pot"
(budget bucket) it was charged to. You work for MissionLedger, a budgeting app
used by households, small nonprofits, and small businesses in the US.

Given the transaction (date, merchant, description, amount) and the pot's rules
(type, remaining balance, monthly limit, allowed/disallowed categories, grant
window dates, grantor), do two things:
1. Suggest a short spending category for the transaction (e.g. "Groceries",
   "Software", "Travel", "Office Supplies").
2. Flag any rule violations in plain language, for example: spending over the
   monthly limit, spending on a disallowed category, spending outside a grant's
   allowed categories, or spending after a grant/pot's end date.

Only warn about rules you were actually given — never invent a rule. If nothing
is wrong, return an empty warnings list. Keep warnings short and specific
enough for a non-technical person to act on. Never recommend ignoring a
warning or bypassing approval.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )


async def review_transaction(
    db: Session,
    *,
    pot: models.Pot,
    date,
    merchant: str,
    description: str | None,
    amount: float,
    workspace_id: int,
    user_id: int,
) -> TransactionReview:
    pot_rules = {
        "pot_name": pot.name,
        "pot_type": pot.type.value,
        "current_balance": pot.current_balance,
        "budget_or_grant_amount": pot.budget_or_grant_amount,
        "monthly_limit": pot.monthly_limit,
        "allowed_categories": pot.allowed_categories,
        "disallowed_categories": pot.disallowed_categories,
        "grantor": pot.grantor,
        "start_date": pot.start_date.isoformat() if pot.start_date else None,
        "end_date": pot.end_date.isoformat() if pot.end_date else None,
    }
    prompt = (
        f"Transaction: {wrap_untrusted(merchant)}, ${amount:,.2f}, on {date.isoformat()}. "
        f"Description: {wrap_untrusted(description or 'none given')}.\n"
        f"Pot rules: {pot_rules}"
    )

    agent = build_transaction_review_agent(db)
    result = await agent.run(prompt, usage_limits=UsageLimits(request_limit=MAX_AGENT_REQUESTS))

    log_usage(
        db,
        usage=result.usage,
        purpose="transaction_review",
        workspace_id=workspace_id,
        user_id=user_id,
        request_id=str(uuid.uuid4()),
    )
    return result.output
