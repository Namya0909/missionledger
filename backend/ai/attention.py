"""Explains the problems Python already found (see rules.py) in plain language with a
suggested fix. One batched call for the whole "Needs attention" box, not one call per
issue — keeps this cheap regardless of how many issues there are (Lecture 11, tokenomics).

The AI never decides *whether* something is a problem or computes any number here —
rules.find_issues() already did that math. It only explains issues it's handed.
"""

import uuid

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from sqlalchemy.orm import Session

from ai.core import MAX_AGENT_REQUESTS, NO_REASONING, get_model, log_usage
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS, wrap_untrusted
from rules import Issue


class ExplainedIssue(BaseModel):
    index: int = Field(description="The 0-based index of the issue this explains, matching the input order.")
    explanation: str = Field(description="One plain-language sentence a non-technical person would understand.")
    suggested_fix: str = Field(description="One short, concrete suggested next step.")


class AttentionExplanations(BaseModel):
    items: list[ExplainedIssue]


def build_attention_agent(db: Session) -> Agent[None, AttentionExplanations]:
    return Agent(
        get_model(db),
        output_type=AttentionExplanations,
        model_settings=NO_REASONING,
        instructions="""
You explain budgeting problems that have already been detected by code, for a
non-technical person running a household, nonprofit, or small business. You are
given a numbered list of already-confirmed issues (over-budget pots, spending outside
a grant's rules, a savings goal falling behind pace). For each one, return its index,
a one-sentence plain-language explanation, and one short concrete suggested fix.

Do not invent numbers, add new issues, or change the facts given — only restate them
simply and suggest a sensible next step (e.g. "move spending to the General Fund",
"ask the board to approve a budget increase", "increase the monthly transfer").
Return exactly one explanation per issue given, in the same order.
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )


async def explain_issues(
    db: Session,
    *,
    issues: list[Issue],
    workspace_id: int,
    user_id: int | None,
    purpose: str = "needs_attention",
) -> list[dict]:
    if not issues:
        return []

    numbered = "\n".join(f"{i}. [{issue.kind}] {issue.detail}" for i, issue in enumerate(issues))
    agent = build_attention_agent(db)
    result = await agent.run(
        f"Issues to explain:\n{wrap_untrusted(numbered)}",
        usage_limits=UsageLimits(request_limit=MAX_AGENT_REQUESTS),
    )
    log_usage(
        db,
        usage=result.usage,
        purpose=purpose,
        workspace_id=workspace_id,
        user_id=user_id,
        request_id=str(uuid.uuid4()),
    )

    explanations = {item.index: item for item in result.output.items}
    out = []
    for i, issue in enumerate(issues):
        explained = explanations.get(i)
        out.append(
            {
                "pot_id": issue.pot_id,
                "pot_name": issue.pot_name,
                "kind": issue.kind,
                "detail": issue.detail,
                "transaction_id": issue.transaction_id,
                "explanation": explained.explanation if explained else issue.detail,
                "suggested_fix": explained.suggested_fix if explained else "Review this pot's rules.",
            }
        )
    return out
