"""Pure-Python cost/token aggregation over AIUsageLog — every number the Costs
page shows is computed here from real, already-logged token counts, the same
"Python computes, nothing is guessed" rule the rest of the app follows.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

import models

PROJECTION_USER_COUNTS = [100, 1_000, 10_000]


@dataclass
class CostsSummary:
    total_requests: int = 0
    total_calls: int = 0
    total_input_tokens: int = 0
    total_cached_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_cost_per_request: float = 0.0
    cache_hit_rate_pct: float = 0.0
    this_month_cost_usd: float = 0.0
    this_month_active_users: int = 0
    cost_per_user_this_month: float = 0.0
    projections: dict[int, float] = field(default_factory=dict)
    by_workspace_type: list[dict] = field(default_factory=list)
    by_purpose: list[dict] = field(default_factory=list)


def compute_summary(db: Session) -> CostsSummary:
    rows = db.query(models.AIUsageLog).all()
    summary = CostsSummary()
    if not rows:
        return summary

    summary.total_calls = len(rows)
    summary.total_input_tokens = sum(r.input_tokens for r in rows)
    summary.total_cached_tokens = sum(r.cached_tokens for r in rows)
    summary.total_output_tokens = sum(r.output_tokens for r in rows)
    summary.total_cost_usd = round(sum(r.cost_usd for r in rows), 4)
    summary.cache_hit_rate_pct = (
        round(summary.total_cached_tokens / summary.total_input_tokens * 100, 1) if summary.total_input_tokens else 0.0
    )

    cost_by_request: dict[str, float] = {}
    for r in rows:
        cost_by_request[r.request_id] = cost_by_request.get(r.request_id, 0.0) + r.cost_usd
    summary.total_requests = len(cost_by_request)
    summary.avg_cost_per_request = (
        round(sum(cost_by_request.values()) / len(cost_by_request), 4) if cost_by_request else 0.0
    )

    today = date.today()
    month_start = datetime(today.year, today.month, 1)
    month_rows = [r for r in rows if r.created_at >= month_start]
    summary.this_month_cost_usd = round(sum(r.cost_usd for r in month_rows), 4)
    active_users = {r.user_id for r in month_rows if r.user_id is not None}
    summary.this_month_active_users = len(active_users)
    summary.cost_per_user_this_month = (
        round(summary.this_month_cost_usd / len(active_users), 4) if active_users else 0.0
    )
    # Linear extrapolation from the real per-user-this-month figure — an
    # estimate, clearly labeled as such on the page, not a guarantee.
    summary.projections = {n: round(summary.cost_per_user_this_month * n, 2) for n in PROJECTION_USER_COUNTS}

    workspace_types = {w.id: w.type.value for w in db.query(models.Workspace).all()}
    by_type: dict[str, dict] = {}
    for r in rows:
        type_name = workspace_types.get(r.workspace_id, "none (setup/account-level)")
        bucket = by_type.setdefault(type_name, {"workspace_type": type_name, "calls": 0, "cost_usd": 0.0, "tokens": 0})
        bucket["calls"] += 1
        bucket["cost_usd"] += r.cost_usd
        bucket["tokens"] += r.input_tokens + r.output_tokens
    summary.by_workspace_type = [
        {**v, "cost_usd": round(v["cost_usd"], 4)} for v in sorted(by_type.values(), key=lambda b: -b["cost_usd"])
    ]

    by_purpose: dict[str, dict] = {}
    for r in rows:
        bucket = by_purpose.setdefault(r.purpose, {"purpose": r.purpose, "calls": 0, "cost_usd": 0.0, "tokens": 0})
        bucket["calls"] += 1
        bucket["cost_usd"] += r.cost_usd
        bucket["tokens"] += r.input_tokens + r.output_tokens
    summary.by_purpose = [
        {**v, "cost_usd": round(v["cost_usd"], 4)} for v in sorted(by_purpose.values(), key=lambda b: -b["cost_usd"])
    ]

    return summary


def compute_daily_series(db: Session, *, days: int = 30) -> list[dict]:
    """One row per (day, purpose) for the last `days` days — shaped for a
    stacked/multi-line chart of tokens per day by agent."""
    cutoff = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    rows = db.query(models.AIUsageLog).filter(models.AIUsageLog.created_at >= cutoff).all()
    buckets: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.created_at.date().isoformat(), r.purpose)
        buckets[key] = buckets.get(key, 0) + r.input_tokens + r.output_tokens
    return [{"date": d, "purpose": p, "tokens": tokens} for (d, p), tokens in sorted(buckets.items())]


def raw_rows(db: Session) -> list[models.AIUsageLog]:
    return db.query(models.AIUsageLog).order_by(models.AIUsageLog.created_at.desc()).all()
