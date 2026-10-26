"""App-wide Costs page — not scoped to one workspace. Gated to anyone who is
privileged (admin/treasurer/owner) in at least one workspace they belong to,
via permissions.is_privileged_anywhere.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import costs
import models
import schemas
from auth import get_current_user
from config import AI_MODEL_NAME
from database import get_db
from permissions import is_privileged_anywhere

router = APIRouter(prefix="/costs", tags=["costs"])


def _require_privileged(db: Session, current_user: models.User) -> None:
    memberships = db.query(models.Membership).filter(models.Membership.user_id == current_user.id).all()
    if not is_privileged_anywhere(memberships):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You need an admin/treasurer/owner role in at least one workspace to view costs.",
        )


@router.get("/summary", response_model=schemas.CostsSummaryOut)
def get_costs_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    summary = costs.compute_summary(db)
    return schemas.CostsSummaryOut(
        total_requests=summary.total_requests,
        total_calls=summary.total_calls,
        total_input_tokens=summary.total_input_tokens,
        total_cached_tokens=summary.total_cached_tokens,
        total_output_tokens=summary.total_output_tokens,
        total_cost_usd=summary.total_cost_usd,
        avg_cost_per_request=summary.avg_cost_per_request,
        cache_hit_rate_pct=summary.cache_hit_rate_pct,
        this_month_cost_usd=summary.this_month_cost_usd,
        this_month_active_users=summary.this_month_active_users,
        cost_per_user_this_month=summary.cost_per_user_this_month,
        projections=summary.projections,
        by_workspace_type=summary.by_workspace_type,
        by_purpose=summary.by_purpose,
        # config.py's MODEL_PRICING dict is documented as an unverified placeholder
        # for gpt-6-luna — every dollar figure here inherits that caveat until a
        # real course/Portkey rate replaces it.
        pricing_is_placeholder=True,
        model_name=AI_MODEL_NAME,
    )


@router.get("/daily", response_model=list[schemas.DailyTokensOut])
def get_costs_daily(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    return costs.compute_daily_series(db, days=days)


@router.get("/raw", response_model=list[schemas.AIUsageOut])
def get_costs_raw(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    return costs.raw_rows(db)
