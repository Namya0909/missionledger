"""The Orchestrator: the chat endpoint's front door. It decides whether a message
is a question for the Analyst, a request to log a new expense, or something else
(e.g. a report request, which it answers directly by pointing at the Reports tab
rather than generating anything itself — report generation is a dedicated button,
not a chat action).

Ground rules, enforced structurally rather than just by prompt wording:
- `request_limit=6` on the run below is the literal "no more than 6 steps" cap —
  PydanticAI already counts every tool round-trip against this, so a message that
  tried to bounce between tools forever would simply fail closed instead of looping.
- The only tool anywhere in this file (or the Analyst it delegates to) that writes
  to the database is log_expense_as_waiting, and it only ever creates a *pending*
  transaction — never approves, rejects, or changes a rule.
- workspace_id and user_id are both closures captured from the authenticated
  caller's membership (see routers/chat.py) — never a value the model can set.
"""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import response_cache
from ai.chat import build_chat_agent
from ai.core import NO_REASONING, get_model, log_usage
from ai.gatekeeper import check_message
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS, wrap_untrusted
from ai.trace import TraceStep, extract_trace
from audit import log_action
from feature_flags import is_enabled
from models import TransactionStatus
from pii import redact_pii
from rules import pot_usage
from security_log import log_security_event

logger = logging.getLogger(__name__)

ORCHESTRATOR_REQUEST_LIMIT = 6
# The Analyst's own tool-use budget for one question — separate from the
# Orchestrator's 6-step cap above. A compound question ("this month, including
# the statement I just uploaded") can need several tool calls plus a final
# synthesis step, so this is deliberately more generous than the shared
# MAX_AGENT_REQUESTS used for simpler single-purpose agents elsewhere.
ANALYST_REQUEST_LIMIT = 8
REQUEST_TIMEOUT_SECONDS = 30
DAILY_TOKEN_BUDGET = 200_000

# A fast, deterministic pre-filter — catches the common phrasings of "give me
# investment/tax/legal advice" before any model call at all (saves tokens, and
# doesn't depend on the LLM's own judgment for something this safety-critical).
# The Gatekeeper and Analyst instructions also decline this if phrased in a way
# this regex misses — this is a backstop, not the only layer.
FINANCIAL_ADVICE_RE = re.compile(
    r"\b(which|what)\s+stocks?\b"
    r"|\bstocks?\s+(should|to)\s+(i|we)\s+buy\b"
    r"|\bbuy\s+(shares|stock|crypto|bitcoin|a stock)\b"
    r"|\binvest(ment)?\s+advice\b"
    r"|\bshould\s+(i|we)\s+invest\b"
    r"|\bcan\s+(i|we)\s+deduct\b"
    r"|\btax[- ]deduct(ible|ion)\b"
    r"|\bis\s+(this|it)\s+legal\b"
    r"|\blegal\s+advice\b",
    re.IGNORECASE,
)
FINANCIAL_ADVICE_DECLINE = (
    "I can't give specific investment, tax, or legal advice. This is not financial, "
    "tax, or legal advice. Check with a CPA or advisor."
)

DOLLAR_AMOUNT_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
NUMBER_TOLERANCE = 1.0


@dataclass
class OrchestratorDeps:
    """Shared, mutable state threaded through the run via RunContext.deps — lets a
    tool (ask_analyst) record its own nested trace and token usage back up to
    handle_chat_request, which can't see inside a tool call otherwise."""

    nested_trace: list[TraceStep] = field(default_factory=list)
    usage_logs: list[models.AIUsageLog] = field(default_factory=list)


def build_orchestrator_agent(db: Session, workspace_id: int, user_id: int, request_id: str) -> Agent[OrchestratorDeps, str]:
    instructions = """
You are the front door for MissionLedger's AI helpers on one workspace. For every
message, decide what the person wants and act:

- A question about this workspace's money (balances, spending, affordability,
  savings projections, payroll coverage, flagged issues, who owes whom, what's
  pending) → call ask_analyst with the question, then relay its answer back
  WORD-FOR-WORD INCLUDING EVERY NUMBER, NAME, AND AMOUNT IT GAVE YOU. Do not
  summarize, shorten, or compress a list it gave you (e.g. if it names three
  people and a dollar amount for each, your reply must include all three names
  AND all three amounts — never collapse them into "each owe X" with the
  amounts dropped). You may lightly rephrase its wording, but never at the cost
  of dropping a figure it stated.
- A request to log/record/add a new expense they just made (e.g. "log $40 at
  Walmart for groceries") → call log_expense_as_waiting with the pot, merchant,
  amount, category, and a short description you infer from their words. Always
  tell them in your reply that it's now waiting for someone to approve it — you
  are not approving anything.
- A request for a report, summary PDF, or "money check-in" document → do NOT call
  any tool; just reply that they can generate that from the Reports tab.
- Anything else (off-topic, asking you to approve/reject/change a rule, or asking
  for specific investment/tax/legal advice) → decline briefly. For investment/tax/
  legal advice specifically, say: "This is not financial, tax, or legal advice.
  Check with a CPA or advisor."

Never state a number yourself — only relay what ask_analyst or log_expense_as_waiting
actually returned.
"""
    if not is_enabled("cache_friendly_prompts"):
        instructions = f"(call id {time.time_ns()})\n" + instructions

    agent = Agent(
        get_model(db),
        output_type=str,
        deps_type=OrchestratorDeps,
        model_settings=NO_REASONING,
        instructions=instructions + UNTRUSTED_DATA_INSTRUCTIONS,
    )

    @agent.tool
    async def ask_analyst(ctx: RunContext[OrchestratorDeps], question: str) -> str:
        """Ask the read-only Analyst a question about this workspace's pots,
        transactions, budgets, grants, goals, or who owes whom. Returns its
        grounded answer as plain text, or a short apology if the Analyst itself
        hit a problem — this tool must never raise, since an unhandled error here
        would blow up the Orchestrator's whole run and discard everything already
        traced (the Gatekeeper step, token usage so far), leaving the user with a
        generic fallback that looks like a security block but isn't one."""
        try:
            analyst_agent = build_chat_agent(db, workspace_id)
            analyst_result = await analyst_agent.run(question, usage_limits=UsageLimits(request_limit=ANALYST_REQUEST_LIMIT))
        except Exception as exc:
            logger.warning("Analyst call failed for workspace %s: %s", workspace_id, exc)
            ctx.deps.nested_trace.append(TraceStep(helper="Analyst", tool=None, args=None, result=f"failed: {exc}"))
            return "I ran into a problem looking that up — try asking a more specific or simpler question."
        usage_log = log_usage(
            db, usage=analyst_result.usage, purpose="chat_assistant",
            workspace_id=workspace_id, user_id=user_id, request_id=request_id,
        )
        # ctx.deps is shared state threaded from handle_chat_request — recording the
        # Analyst's own tool calls and token usage here is what lets "Behind the
        # scenes" drill into *how* it answered and what it cost, not just that it
        # was asked. The summary step (no tool) carries the Analyst's own real
        # token/cost numbers; the extracted steps after it are its tool calls.
        ctx.deps.nested_trace.append(
            TraceStep(
                helper="Analyst", tool=None, args=None, result="(own reasoning, not a tool call)",
                input_tokens=usage_log.input_tokens, cached_tokens=usage_log.cached_tokens,
                output_tokens=usage_log.output_tokens, cost_usd=usage_log.cost_usd,
            )
        )
        ctx.deps.nested_trace.extend(extract_trace("Analyst", analyst_result.all_messages()))
        ctx.deps.usage_logs.append(usage_log)
        return analyst_result.output

    @agent.tool
    def log_expense_as_waiting(
        ctx: RunContext[OrchestratorDeps],
        pot_name: str,
        merchant: str,
        amount: float,
        category: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a new expense in this workspace. It always starts pending/waiting
        for a human to approve — this tool can never approve, reject, or skip that
        step, no matter what the user asks. Returns the created expense's summary,
        or a note if no pot matches pot_name."""
        pot = (
            db.query(models.Pot)
            .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
            .first()
        )
        if pot is None:
            pot_names = [p.name for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()]
            return {"created": False, "note": f"No pot named '{pot_name}' found. Pots in this workspace: {pot_names}"}

        transaction = models.Transaction(
            workspace_id=workspace_id,
            pot_id=pot.id,
            date=date.today(),
            merchant=merchant,
            description=description,
            amount=amount,
            category=category,
            source=models.TransactionSource.typed,
            warnings=[],
            status=TransactionStatus.pending,
            created_by_user_id=user_id,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        log_action(
            db,
            action="transaction.created_via_chat",
            workspace_id=workspace_id,
            user_id=user_id,
            details={"transaction_id": transaction.id, "pot_name": pot.name, "amount": amount},
        )
        return {
            "created": True,
            "transaction_id": transaction.id,
            "pot_name": pot.name,
            "merchant": merchant,
            "amount": amount,
            "status": "pending",
        }

    return agent


@dataclass
class RequestCost:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def _sum_cost(usage_logs: list[models.AIUsageLog]) -> RequestCost:
    cost = RequestCost()
    for log in usage_logs:
        cost.input_tokens += log.input_tokens
        cost.cached_tokens += log.cached_tokens
        cost.output_tokens += log.output_tokens
        cost.cost_usd += log.cost_usd
    return cost


def _tokens_used_today(db: Session, user_id: int) -> int:
    today_start = datetime.combine(date.today(), datetime.min.time())
    total = (
        db.query(func.sum(models.AIUsageLog.input_tokens + models.AIUsageLog.output_tokens))
        .filter(models.AIUsageLog.user_id == user_id, models.AIUsageLog.created_at >= today_start)
        .scalar()
    )
    return total or 0


def _numbers_in(text: str) -> set[float]:
    found = set()
    for match in re.finditer(r"-?[\d,]+(?:\.\d+)?", text):
        try:
            found.add(float(match.group().replace(",", "")))
        except ValueError:
            continue
    return found


def _reply_numbers_are_grounded(reply: str, trace: list[TraceStep]) -> bool:
    """Every dollar amount the reply states must be traceable (within $1) to
    something a tool actually returned this turn — the mechanical version of
    "don't make up a number." Only checks $-prefixed amounts in the reply
    (the figures a user would actually act on), against every number that
    appeared anywhere in any tool result this turn."""
    reply_amounts = [float(m.group(1).replace(",", "")) for m in DOLLAR_AMOUNT_RE.finditer(reply)]
    if not reply_amounts:
        return True
    tool_numbers: set[float] = set()
    for step in trace:
        tool_numbers |= _numbers_in(step.result)
    for amount in reply_amounts:
        if not any(abs(amount - n) <= NUMBER_TOLERANCE for n in tool_numbers):
            return False
    return True


# "python_prefilter" savings flag: a simple, unambiguous "how much is left in
# <pot>" question is answered straight from the database in Python, skipping
# the Gatekeeper and Orchestrator entirely — zero AI calls for the common case.
POT_BALANCE_RE = re.compile(
    r"how much(?:'s| is)\s+(?:left|remaining)\s+(?:in|for)\s+(?:the\s+)?(.+?)\s*\??$",
    re.IGNORECASE,
)


def _try_python_prefilter(db: Session, *, workspace_id: int, message: str) -> str | None:
    match = POT_BALANCE_RE.search(message.strip())
    if not match:
        return None
    pot_name = match.group(1).strip()
    pot = (
        db.query(models.Pot)
        .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
        .first()
    )
    if pot is None:
        return None  # not confident enough to answer — fall through to the full pipeline
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    usage = pot_usage(pot, transactions, date.today())
    if usage.limit is None:
        return f"'{pot.name}' doesn't have a budget or limit set, so there's nothing to compare it against."
    remaining = usage.limit - usage.used
    return f"'{pot.name}' has ${remaining:,.2f} left ({usage.period}), based on its pots record."


async def handle_chat_request(
    db: Session,
    *,
    workspace_id: int,
    user_id: int,
    message: str,
) -> tuple[str, bool, list[TraceStep], RequestCost]:
    """Returns (reply, blocked, trace, cost). Never raises except MissingAIKeyError,
    matching every other AI call site's contract in this app."""
    trace: list[TraceStep] = []
    usage_logs: list[models.AIUsageLog] = []
    request_id = str(uuid.uuid4())

    # PII redaction runs before ANY AI call sees the message, including the Gatekeeper.
    message, pii_counts = redact_pii(message)
    if pii_counts:
        summary = ", ".join(f"{n} {label}" for label, n in pii_counts.items())
        log_security_event(
            db, defense="PII Redaction", action="redacted",
            detail=f"Redacted {summary} from a chat message before sending it to the AI.",
            workspace_id=workspace_id, user_id=user_id,
        )

    # "response_cache" savings flag: an identical question asked again within 10
    # minutes skips every check below and returns the exact same answer, free.
    if is_enabled("response_cache"):
        cached = response_cache.get(workspace_id, message)
        if cached is not None:
            cached_reply, cached_trace = cached
            hit_trace = [TraceStep(helper="Response Cache", tool=None, args=None, result="hit — reused answer from within the last 10 minutes")]
            hit_trace.extend(cached_trace)
            return cached_reply, False, hit_trace, RequestCost()

    # A fast, free, deterministic check — never calls a model for this.
    if FINANCIAL_ADVICE_RE.search(message):
        log_security_event(
            db, defense="Financial Advice Guard", action="declined",
            detail="Declined a request for specific investment/tax/legal advice before any AI call.",
            workspace_id=workspace_id, user_id=user_id,
        )
        return FINANCIAL_ADVICE_DECLINE, True, trace, RequestCost()

    tokens_today = _tokens_used_today(db, user_id)
    if tokens_today >= DAILY_TOKEN_BUDGET:
        log_security_event(
            db, defense="Rate Limiting", action="throttled",
            detail=f"Daily AI token budget reached ({tokens_today:,}/{DAILY_TOKEN_BUDGET:,}).",
            workspace_id=workspace_id, user_id=user_id,
        )
        return (
            "You've reached today's AI usage limit for your account. It resets tomorrow — "
            "you can still use the rest of the app normally.",
            True,
            trace,
            RequestCost(),
        )

    # "python_prefilter" savings flag: try the Python fast path before any AI call.
    if is_enabled("python_prefilter"):
        prefiltered = _try_python_prefilter(db, workspace_id=workspace_id, message=message)
        if prefiltered is not None:
            trace.append(TraceStep(helper="Python Prefilter", tool=None, args=None, result="matched a simple pot-balance question — answered without any AI call"))
            return prefiltered, False, trace, RequestCost()

    verdict, gatekeeper_usage = await check_message(db, message=message, workspace_id=workspace_id, user_id=user_id, request_id=request_id)
    usage_logs.append(gatekeeper_usage)
    trace.append(
        TraceStep(
            helper="Gatekeeper", tool=None, args=None,
            result=f"blocked: {verdict.reason}" if verdict.blocked else "allowed",
            input_tokens=gatekeeper_usage.input_tokens, cached_tokens=gatekeeper_usage.cached_tokens,
            output_tokens=gatekeeper_usage.output_tokens, cost_usd=gatekeeper_usage.cost_usd,
        )
    )
    if verdict.blocked:
        log_security_event(
            db, defense="Gatekeeper", action="blocked",
            detail=f"Blocked chat message: {verdict.reason} (message: {message!r})",
            workspace_id=workspace_id, user_id=user_id,
        )
        return verdict.reason, True, trace, _sum_cost(usage_logs)

    # deps.nested_trace collects the Analyst's own internal tool calls (filled in by
    # the ask_analyst tool below). Kept separate from the Orchestrator's own trace so
    # the final order reads as a drill-down — "Orchestrator asked the Analyst X,
    # here's what the Analyst looked up" — instead of appearing before it happened.
    deps = OrchestratorDeps()
    agent = build_orchestrator_agent(db, workspace_id, user_id, request_id)
    try:
        result = await asyncio.wait_for(
            agent.run(
                f"User message: {wrap_untrusted(message)}",
                deps=deps,
                usage_limits=UsageLimits(request_limit=ORCHESTRATOR_REQUEST_LIMIT),
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        log_security_event(
            db, defense="Rate Limiting", action="timed_out",
            detail=f"Chat request exceeded the {REQUEST_TIMEOUT_SECONDS}s time limit and was cut off.",
            workspace_id=workspace_id, user_id=user_id,
        )
        trace.extend(deps.nested_trace)
        return "That took too long to answer — try a simpler or more specific question.", True, trace, _sum_cost(usage_logs + deps.usage_logs)

    orchestrator_usage = log_usage(db, usage=result.usage, purpose="orchestrator", workspace_id=workspace_id, user_id=user_id, request_id=request_id)
    trace.append(
        TraceStep(
            helper="Orchestrator", tool=None, args=None, result="(own reasoning, not a tool call)",
            input_tokens=orchestrator_usage.input_tokens, cached_tokens=orchestrator_usage.cached_tokens,
            output_tokens=orchestrator_usage.output_tokens, cost_usd=orchestrator_usage.cost_usd,
        )
    )
    trace.extend(extract_trace("Orchestrator", result.all_messages()))
    trace.extend(deps.nested_trace)
    usage_logs.append(orchestrator_usage)
    usage_logs.extend(deps.usage_logs)

    reply = result.output
    if not _reply_numbers_are_grounded(reply, trace):
        log_security_event(
            db, defense="Number Verification", action="replaced",
            detail=f"Reply contained a dollar amount not found in any tool result this turn: {reply!r}",
            workspace_id=workspace_id, user_id=user_id,
        )
        reply = (
            "I couldn't verify one of the numbers in that answer, so here's a safe response "
            "instead: please ask me again, more specifically."
        )

    if is_enabled("response_cache"):
        response_cache.set(workspace_id, message, (reply, trace))

    return reply, False, trace, _sum_cost(usage_logs)
