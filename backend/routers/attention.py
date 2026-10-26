import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
import schemas
from ai.attention import explain_issues
from auth import get_current_user, require_membership
from database import get_db
from rules import find_issues

router = APIRouter(prefix="/workspaces/{workspace_id}/attention", tags=["attention"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[schemas.AttentionItemOut])
async def get_attention(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    recurring_charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()

    issues = find_issues(pots, transactions, date.today(), recurring_charges)

    # Python already found these issues — if the AI explainer call itself fails (rate
    # limit, provider error, or no key configured at all), still show the raw facts
    # rather than hiding real problems. Unlike adding an expense, nothing here writes
    # money, so there's no reason to block the whole dashboard over an AI outage.
    try:
        return await explain_issues(db, issues=issues, workspace_id=workspace_id, user_id=current_user.id)
    except Exception:
        logger.exception("Needs-attention explainer failed for workspace %s", workspace_id)
        return [
            {
                "pot_id": issue.pot_id,
                "pot_name": issue.pot_name,
                "kind": issue.kind,
                "detail": issue.detail,
                "transaction_id": issue.transaction_id,
                "explanation": issue.detail,
                "suggested_fix": "Review this pot's rules.",
            }
            for issue in issues
        ]
