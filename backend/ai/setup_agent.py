"""The Setup Agent: turns one sentence into an editable plan for a workspace.

Two AI calls, each with a fixed structured-output schema (retried once on failure,
then a friendly error — never a crash):
1. One short, natural follow-up question per turn (up to 4), reading the whole
   conversation fresh each time so nothing already said is lost or re-asked.
2. Once enough is known, a single call that drafts suggested pots, approval
   settings, who to invite, and a plain-English summary.

Python, not the AI, enforces the 4-question cap, does every dollar-and-date
calculation (especially the savings-feasibility math), and performs the actual
database writes once the user confirms the (possibly edited) plan. The AI only
ever proposes text and structure for a human to review — nothing is saved until
POST /setup/create.
"""

import json
import logging
import secrets
import uuid
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from sqlalchemy.orm import Session

import models
import schemas
from ai.core import MAX_AGENT_REQUESTS, NO_REASONING, get_model, log_usage
from audit import log_action
from tax_config import DEFAULT_SALES_TAX_RATE, STATE_SALES_TAX_RATES

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 4
DAYS_PER_MONTH = 30.44  # average — good enough for a rough monthly-savings estimate

# STATE_SALES_TAX_RATES/DEFAULT_SALES_TAX_RATE now live in tax_config.py (imported
# above) — the Tax Prep Pack's sales-tax worksheet shares the exact same estimate
# table this pot-sizing step already used, instead of each keeping its own copy.


# ---------------------------------------------------------------------------
# Turn 1..4: the conversational Q&A
# ---------------------------------------------------------------------------

class GrantInfo(BaseModel):
    name: str = Field(description="Short name for the grant.")
    amount: float | None = None
    allowed_categories: list[str] = Field(default_factory=list, description="What the grant can pay for.")
    end_date: str | None = Field(default=None, description="ISO date (YYYY-MM-DD) if known.")


class BillInfo(BaseModel):
    name: str
    amount: float | None = None


class SetupCollected(BaseModel):
    # group
    member_count: int | None = None
    shared_bills: list[BillInfo] = Field(default_factory=list)
    goal_name: str | None = None
    goal_amount: float | None = None
    goal_date: str | None = Field(default=None, description="ISO date (YYYY-MM-DD) if known.")
    monthly_capacity: float | None = Field(
        default=None, description="How much they said they can realistically put toward the goal each month."
    )
    split_method: Literal["equal", "income", "custom"] | None = None
    # nonprofit
    grants: list[GrantInfo] = Field(default_factory=list)
    # business
    state: str | None = Field(default=None, description="Two-letter US state code.")
    monthly_sales: float | None = None
    has_payroll: bool | None = None
    payroll_amount: float | None = None
    payday: str | None = None


class SetupTurnResult(BaseModel):
    in_scope: bool = Field(description="False if this isn't about setting up a budgeting workspace.")
    decline_reason: str | None = Field(default=None, description="One polite sentence, only when in_scope is false.")
    workspace_type: Literal["group", "nonprofit", "business"] | None = None
    reply: str = Field(description="The next short question to ask, or a brief wrap-up line once done.")
    ready_to_create: bool = Field(
        default=False, description="True once every required field for this workspace type is filled in."
    )
    collected: SetupCollected = Field(default_factory=SetupCollected)


def build_qa_agent(db: Session) -> Agent[None, SetupTurnResult]:
    return Agent(
        get_model(db),
        output_type=SetupTurnResult,
        model_settings=NO_REASONING,
        instructions="""
You are the MissionLedger Setup Agent. You turn one sentence into a configured
budgeting workspace — a group (1-10 people — a solo saver, a couple, a family, or
roommates — sharing or tracking money), a nonprofit, or a small business. You ONLY
help set up a budgeting workspace. If the message is about anything else, set
in_scope=false with a one-sentence polite decline, and nothing else.

A "group" is valid even for exactly one person — e.g. someone saving solo for a
goal. NEVER decline or treat the request as out of scope just because it turns
out to be for one person; that is still a completely normal group of one (they
can always invite others to it later). Only decline for things that truly have
nothing to do with budgeting (e.g. "what's the capital of France").

You read the WHOLE conversation so far on every turn (it's given to you as the
message history) and re-extract everything into `collected` fresh each time —
carry forward every value already given, never lose or re-ask for something the
user already told you. If they volunteer something before you asked for it (e.g.
they mention their state while answering a different question), grab it and skip
asking for it later.

First, classify workspace_type from context:
- "group": a couple, family, roommates, friends sharing money or a trip.
- "nonprofit": they mention a grant, board, volunteers, being a treasurer.
- "business": a shop, store, sales, payroll, being an owner.

Then collect, asking ONE short, warm, conversational question at a time — never a
list, never robotic. React to specifics they just gave you (e.g. if they said
"Connecticut", open with "Connecticut, got it —" before your next question; if they
named a dollar figure, use it back to them). Vary your phrasing — don't always
start the same way.
- group: if there's a savings goal, ask for the goal, its target date, AND about
  how much they can realistically put toward it each month, ALL in one question —
  this one matters most, ask it before anything else. Only after that, if
  relevant, ask about shared bills, how many people (1-10, solo is fine), and how
  they want to split costs (equally / by income / custom percentages) — skip any
  of these the conversation doesn't need (e.g. don't ask "how many people" if
  they already said "my wife" or "just me").
- nonprofit: each grant's name, amount, what it can be spent on, and when it ends.
- business: their US state, typical monthly sales, whether they have payroll (and
  its monthly amount), and payday schedule.

Never invent a number or date the user didn't give you — if something is missing,
ask for it in `reply` instead of guessing, and leave that field null in `collected`.
A vague date like "next August" or "this summer" is specific ENOUGH — pick a
sensible exact date yourself (e.g. the 1st of that month) and move on; do not ask
the user to narrow it down further.

Set ready_to_create=true only once you have enough to make a useful plan: group
needs the goal amount+date (monthly_capacity is nice to have but not required —
ask once, don't block forever on it), OR at least one shared bill; nonprofit needs
at least one grant with an amount; business needs at least the state and monthly
sales. When ready, `reply` must be a short, warm wrap-up line (e.g. "Love it —
let's put together a plan for you two." or "Great, I've got what I need — one
sec..."), NEVER a question — if `reply` asks the user anything, ready_to_create
must be false.

If the user's own words give you a count (e.g. "two grants", "the four of us"),
treat that count as the real target — keep asking, one at a time, until you have
that many, before setting ready_to_create=true. Don't stop at the generic minimum
above if the user told you to expect more than that.

You will never be asked more than 4 questions total — if you're told this is the
last turn, finish with whatever you have instead of asking for more.
""",
    )


def _history_to_prompt(history: list[dict], message: str) -> str:
    lines = [f"{h['role']}: {h['content']}" for h in history]
    lines.append(f"user: {message}")
    return "\n".join(lines)


async def _run_with_retry(agent: Agent, prompt: str, *, request_limit: int):
    """Structured output is schema-validated by pydantic_ai already, but a transient
    provider hiccup (truncated response, brief outage) can still fail a call outright.
    Retry once; only then let the caller show a friendly error instead of crashing."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return await agent.run(prompt, usage_limits=UsageLimits(request_limit=request_limit))
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            last_error = exc
            logger.warning("Setup Agent call failed (attempt %d/2): %s", attempt + 1, exc)
    raise last_error


async def run_setup_turn(
    db: Session,
    *,
    user_id: int,
    history: list[dict],
    message: str,
) -> tuple[SetupTurnResult | None, int, str | None]:
    """Runs one Q&A turn. Returns (result, question_number, error). `result` is None
    only if both attempts failed — `error` then holds a friendly message to show."""
    questions_already_asked = sum(1 for h in history if h["role"] == "assistant")
    is_last_allowed_turn = questions_already_asked >= MAX_QUESTIONS - 1

    agent = build_qa_agent(db)
    prompt = _history_to_prompt(history, message)
    if is_last_allowed_turn:
        prompt += "\n\n(This is the last turn allowed — finish with ready_to_create=true using what you have.)"

    try:
        result = await _run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    except Exception:
        return None, questions_already_asked, "Something went wrong on my end — mind trying that again?"

    log_usage(db, usage=result.usage, purpose="setup_agent_question", workspace_id=None, user_id=user_id, request_id=str(uuid.uuid4()))
    turn = result.output

    # Safety net, not just a prompt hope: a reply that's still asking something is
    # never "ready" — this caught a real case where the model asked for a second
    # grant's details in `reply` while also (wrongly) setting ready_to_create=true.
    if turn.ready_to_create and not is_last_allowed_turn and turn.reply.rstrip().endswith("?"):
        turn.ready_to_create = False

    if is_last_allowed_turn and turn.in_scope:
        turn.ready_to_create = True

    if not turn.in_scope:
        question_number = 0  # declined — no question was asked
    elif turn.ready_to_create:
        question_number = questions_already_asked  # wrap-up line, not a new question
    else:
        question_number = questions_already_asked + 1

    return turn, min(question_number, MAX_QUESTIONS), None


# ---------------------------------------------------------------------------
# Savings math — pure Python, the AI never computes this
# ---------------------------------------------------------------------------

def compute_savings_analysis(collected: SetupCollected) -> schemas.SavingsAnalysisOut | None:
    if collected.goal_amount is None or not collected.goal_date:
        return None
    deadline = _parse_date(collected.goal_date)
    if deadline is None:
        return None

    today = date.today()
    days_left = max((deadline - today).days, 1)
    months_left = round(days_left / DAYS_PER_MONTH, 2)
    required_monthly = round(collected.goal_amount / months_left, 2)

    capacity = collected.monthly_capacity
    if not capacity or capacity <= 0:
        return schemas.SavingsAnalysisOut(
            goal_amount=collected.goal_amount, months_left=months_left, required_monthly=required_monthly,
            monthly_capacity=None, feasible=True, shortfall_per_month=None, options=[],
        )

    if required_monthly <= capacity:
        return schemas.SavingsAnalysisOut(
            goal_amount=collected.goal_amount, months_left=months_left, required_monthly=required_monthly,
            monthly_capacity=capacity, feasible=True, shortfall_per_month=0.0, options=[],
        )

    shortfall = round(required_monthly - capacity, 2)
    months_needed_at_capacity = collected.goal_amount / capacity
    pushed_back_deadline = today + timedelta(days=round(months_needed_at_capacity * DAYS_PER_MONTH))
    achievable_goal = round(capacity * months_left, 2)

    options = [
        f"Push the date to about {pushed_back_deadline.strftime('%B %Y')} "
        f"(~{round(months_needed_at_capacity, 1)} months) to still hit the full ${collected.goal_amount:,.0f}.",
        f"Lower the goal to about ${achievable_goal:,.0f} to make it by "
        f"{deadline.strftime('%B %Y')} at ${capacity:,.0f}/month.",
        f"Find about ${shortfall:,.0f} more per month elsewhere in the budget to close the gap.",
    ]
    return schemas.SavingsAnalysisOut(
        goal_amount=collected.goal_amount, months_left=months_left, required_monthly=required_monthly,
        monthly_capacity=capacity, feasible=False, shortfall_per_month=shortfall, options=options,
    )


def compute_business_estimates(collected: SetupCollected) -> dict | None:
    """Like compute_savings_analysis, but for the business-specific numbers — the
    plan agent explains these, it never multiplies a tax rate itself."""
    if not collected.monthly_sales:
        return None
    rate = STATE_SALES_TAX_RATES.get((collected.state or "").upper(), DEFAULT_SALES_TAX_RATE)
    return {
        "state_sales_tax_rate": rate,
        "expected_monthly_sales_tax": round(collected.monthly_sales * rate, 2),
        "rate_is_estimate": (collected.state or "").upper() not in STATE_SALES_TAX_RATES,
    }


# ---------------------------------------------------------------------------
# Plan drafting — one more structured-output call, informed by the Python math
# ---------------------------------------------------------------------------

class PlanDraft(BaseModel):
    suggested_name: str = Field(description="A short, friendly workspace name.")
    summary: str = Field(description="2-4 plain-English sentences summarizing the plan.")
    pots: list[schemas.PlanPotOut]
    invites: list[schemas.InviteSuggestionOut]


def build_plan_agent(db: Session) -> Agent[None, PlanDraft]:
    return Agent(
        get_model(db),
        output_type=PlanDraft,
        model_settings=NO_REASONING,
        instructions="""
You draft a MissionLedger setup plan from already-collected facts (given to you
as JSON) — you do not ask questions here, and you do not invent any number, date,
or percentage that isn't already in the facts you were given, including any
savings-math figures (required monthly amount, shortfall, suggested options) —
those were computed by Python and handed to you verbatim; just explain them in
your summary in plain English, do not recompute or alter them.

Suggest one pot per thing mentioned (a bill, a goal, a grant, payroll, operating
cash, sales tax). Each pot has one `deadline` field used two ways: for a goal it's
the target date; for a grant it's when the grant ends — set it from whichever date
the facts gave you for that pot. Use type "savings_goal" ONLY for a one-time goal
with a specific target_amount and date (a vacation, a down payment). Sales Tax
Savings, an emergency reserve, or any other ongoing cushion that just keeps
building up with no fixed target or date is type "reserve" instead, sized by
monthly_limit (the amount expected to come in each month), not target_amount. If
a `business_estimates` fact is given, use its `expected_monthly_sales_tax`
EXACTLY as the Sales Tax Savings pot's monthly_limit — never compute your own
percentage of sales. Recommend approval_required=true with a short approval_reason
specifically for grants and for payroll (e.g. "Grants usually need sign-off before
spending." / "Payroll is a big recurring cost worth a second set of eyes."); leave
approval off elsewhere unless there's a clear reason. Suggest the split_method the
user chose (or "equal" if they shared bills/a goal but didn't say) for group pots.

Suggest who else to invite based on workspace_type: group -> role "member" labeled
"Household members"; nonprofit -> "volunteer" labeled "Volunteers" and
"board_member" labeled "Board members"; business -> "staff" labeled "Staff" and
"bookkeeper" labeled "Bookkeeper". Only suggest roles that make sense given what
they told you (e.g. don't suggest a bookkeeper invite for a solo coffee cart).

Write `summary` like you're handing this to the person, not documenting it —
warm, brief, and concrete (use the real numbers). If a savings analysis was
provided and it's not feasible, say so plainly and mention that there are a few
ways to adjust it (without inventing which ones — those are shown separately).
""",
    )


def _plan_prompt(
    workspace_type: str,
    collected: SetupCollected,
    savings: schemas.SavingsAnalysisOut | None,
    business_estimates: dict | None,
) -> str:
    parts = [f"workspace_type: {workspace_type}", f"collected: {collected.model_dump_json()}"]
    if savings:
        parts.append(f"savings_analysis (already computed by Python, do not recompute): {savings.model_dump_json()}")
    if business_estimates:
        parts.append(f"business_estimates (already computed by Python, do not recompute): {json.dumps(business_estimates)}")
    return "\n".join(parts)


async def generate_plan(
    db: Session,
    *,
    user_id: int,
    workspace_type: str,
    collected: SetupCollected,
) -> tuple[schemas.SetupPlanOut | None, str | None]:
    """Returns (plan, error). `plan` is None only if both attempts failed."""
    savings = compute_savings_analysis(collected)
    business_estimates = compute_business_estimates(collected) if workspace_type == "business" else None
    agent = build_plan_agent(db)
    prompt = _plan_prompt(workspace_type, collected, savings, business_estimates)

    try:
        result = await _run_with_retry(agent, prompt, request_limit=MAX_AGENT_REQUESTS)
    except Exception:
        return None, "I couldn't put together a plan just now — want to try again?"

    log_usage(db, usage=result.usage, purpose="setup_agent_plan", workspace_id=None, user_id=user_id, request_id=str(uuid.uuid4()))
    draft = result.output

    # Safety net: the sales-tax pot specifically must be type "reserve" (tracked by
    # monthly_limit, no fixed end) — don't trust the model to always get this right,
    # since mistyping it as "savings_goal" would silently break the reserve-shortfall
    # check this pot exists for.
    if business_estimates:
        for pot in draft.pots:
            if "sales tax" in pot.name.lower() and pot.type != "reserve":
                pot.type = "reserve"
                pot.monthly_limit = pot.monthly_limit or business_estimates["expected_monthly_sales_tax"]
                pot.target_amount = None
                pot.deadline = None

    plan = schemas.SetupPlanOut(
        workspace_type=workspace_type,
        suggested_name=draft.suggested_name,
        summary=draft.summary,
        pots=draft.pots,
        invites=draft.invites,
        savings_analysis=savings,
        state=(collected.state or "").upper() or None if workspace_type == "business" else None,
    )
    return plan, None


# ---------------------------------------------------------------------------
# Finalizing — plain Python, runs only when the user clicks "Create my workspace"
# ---------------------------------------------------------------------------

def finalize_workspace_from_plan(
    db: Session,
    *,
    user: models.User,
    workspace_type: str,
    suggested_name: str,
    pots: list[schemas.PlanPotOut],
    invites: list[schemas.InviteSuggestionOut],
    tax_pack_enabled: bool = False,
    state: str | None = None,
) -> tuple[models.Workspace, list[models.InviteLink]]:
    wtype = models.WorkspaceType(workspace_type)
    role_for_creator = {
        models.WorkspaceType.group: models.Role.admin,
        models.WorkspaceType.nonprofit: models.Role.treasurer,
        models.WorkspaceType.business: models.Role.owner,
    }[wtype]

    workspace = models.Workspace(
        name=suggested_name or "My Workspace",
        type=wtype,
        tax_pack_enabled=tax_pack_enabled,
        state=(state or "").upper() or None,
    )
    db.add(workspace)
    db.flush()
    db.add(models.Membership(user_id=user.id, workspace_id=workspace.id, role=role_for_creator))

    for p in pots:
        is_deposit = p.type in ("savings_goal", "reserve")
        starting_balance = 0.0 if is_deposit else (p.budget_or_grant_amount or 0.0)
        approver_ids = [user.id] if p.approval_required else None
        # The plan UI shows one "date" field per pot (whatever it means for that
        # type); the real Pot model splits that into distinct columns — a savings
        # goal's target date vs. a grant's end date — so map it here.
        is_grant = p.type == "restricted_grant"
        db.add(models.Pot(
            workspace_id=workspace.id, name=p.name, type=models.PotType(p.type),
            budget_or_grant_amount=p.budget_or_grant_amount, current_balance=starting_balance,
            target_amount=p.target_amount, deadline=None if is_grant else p.deadline,
            end_date=p.deadline if is_grant else None, monthly_limit=p.monthly_limit,
            allowed_categories=p.allowed_categories or None,
            split_method=models.SplitMethod(p.split_method) if p.split_method else None,
            approval_required=p.approval_required, approver_user_ids=approver_ids,
        ))

    invite_links: list[models.InviteLink] = []
    for inv in invites:
        link = models.InviteLink(
            workspace_id=workspace.id, role=models.Role(inv.role), label=inv.label,
            token=secrets.token_urlsafe(16), created_by_user_id=user.id,
        )
        db.add(link)
        invite_links.append(link)

    # The Q&A and plan-drafting AI calls happened before this workspace existed, so
    # they were logged with workspace_id=None — attribute them to it now, so its own
    # AI Usage tab shows the real cost of setting it up, not just everything after.
    db.query(models.AIUsageLog).filter(
        models.AIUsageLog.user_id == user.id,
        models.AIUsageLog.workspace_id.is_(None),
        models.AIUsageLog.purpose.in_(["setup_agent_question", "setup_agent_plan"]),
    ).update({"workspace_id": workspace.id})

    db.commit()
    db.refresh(workspace)
    for link in invite_links:
        db.refresh(link)

    log_action(
        db, action="workspace.created_by_setup_agent", workspace_id=workspace.id, user_id=user.id,
        details={"workspace_type": workspace_type, "pot_count": len(pots), "invite_count": len(invite_links)},
    )
    return workspace, invite_links


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
