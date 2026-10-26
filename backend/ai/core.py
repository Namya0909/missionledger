"""Shared AI plumbing: one Portkey/OpenAI client config and one token/cost logger,
used by every agent in the app (transaction reviewer, gatekeeper, chat assistant,
needs-attention explainer). Keeping this in one place is what Lecture 11's
tokenomics tracking and Lecture 12's cost/safety guardrails both depend on.
"""

import logging
from datetime import date, datetime

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from config import (
    AI_MODEL_NAME,
    MODEL_PRICING,
    OPENAI_API_KEY,
    PORTKEY_API_KEY,
    PORTKEY_BASE_URL,
    require_ai_key,
    using_portkey,
)

MAX_AGENT_REQUESTS = 3  # safety cap: bounds cost/runaway tool-calling for any one call

# App-wide ceiling, independent of and on top of ai/orchestrator.py's per-user
# 200,000/day chat limit — this is the whole class's shared course API key, not
# any one person's budget. Checked once, centrally, at the one place every
# agent in the app is built (get_model(), below) — see GlobalAIBudgetExceeded.
GLOBAL_DAILY_TOKEN_LIMIT = 2_000_000

logger = logging.getLogger(__name__)


class GlobalAIBudgetExceeded(RuntimeError):
    """Raised when today's app-wide token usage has hit GLOBAL_DAILY_TOKEN_LIMIT.
    Distinct from MissingAIKeyError (no key at all) so main.py can give callers a
    different, specific, friendly message for each — see check_global_budget()."""


def check_global_budget(db: Session) -> None:
    today_start = datetime.combine(date.today(), datetime.min.time())
    total = (
        db.query(func.sum(models.AIUsageLog.input_tokens + models.AIUsageLog.output_tokens))
        .filter(models.AIUsageLog.created_at >= today_start)
        .scalar()
    ) or 0
    if total >= GLOBAL_DAILY_TOKEN_LIMIT:
        raise GlobalAIBudgetExceeded(
            "MissionLedger's shared AI budget for today is used up — the rest of the app still "
            "works, and AI answers will be back tomorrow."
        )

# gpt-6-luna rejects structured-output/tool calls while "thinking" (reasoning_effort on):
# the Azure-backed endpoint returns 400 "Function tools ... are not supported ... set
# reasoning_effort to 'none'". Every agent here uses either structured output or tools
# (both are function calls under the hood), so this is shared by all of them.
NO_REASONING = OpenAIChatModelSettings(openai_reasoning_effort="none")


def _client(db: Session) -> AsyncOpenAI:
    require_ai_key()
    check_global_budget(db)
    if using_portkey():
        return AsyncOpenAI(
            api_key=PORTKEY_API_KEY,
            base_url=PORTKEY_BASE_URL,
            default_headers={
                "x-portkey-api-key": PORTKEY_API_KEY,
                "User-Agent": "MissionLedger/1.0",
            },
        )
    return AsyncOpenAI(api_key=OPENAI_API_KEY)


def get_model(db: Session) -> OpenAIChatModel:
    return OpenAIChatModel(AI_MODEL_NAME, provider=OpenAIProvider(openai_client=_client(db)))


def _usd_cost(usage: RunUsage) -> float:
    pricing = MODEL_PRICING[AI_MODEL_NAME]
    billable_input = max(usage.input_tokens - usage.cache_read_tokens, 0)
    return (
        billable_input / 1000 * pricing["input_per_1k"]
        + usage.cache_read_tokens / 1000 * pricing["cached_input_per_1k"]
        + usage.output_tokens / 1000 * pricing["output_per_1k"]
    )


async def run_with_retry(agent: Agent, prompt: str, *, request_limit: int):
    """Structured output is schema-validated by pydantic_ai already, but a transient
    provider hiccup (truncated response, brief outage) can still fail a call outright.
    Retry once; only then let the caller show a friendly error instead of crashing.
    Shared copy of the pattern ai/setup_agent.py introduced first."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return await agent.run(prompt, usage_limits=UsageLimits(request_limit=request_limit))
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            last_error = exc
            logger.warning("AI call failed (attempt %d/2): %s", attempt + 1, exc)
    raise last_error


def log_usage(
    db: Session,
    *,
    usage: RunUsage,
    purpose: str,
    workspace_id: int | None,
    user_id: int | None,
    request_id: str,
) -> models.AIUsageLog:
    entry = models.AIUsageLog(
        workspace_id=workspace_id,
        user_id=user_id,
        request_id=request_id,
        purpose=purpose,
        model_name=AI_MODEL_NAME,
        input_tokens=usage.input_tokens,
        cached_tokens=usage.cache_read_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=_usd_cost(usage),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
