"""The Rules Checker: runs on every new expense, whether typed in by hand or
staged by the Intake helper. Python finds the problems (rules.find_issues, scoped
to this one pot) exactly like the Needs Attention box does; the only new part
here is calling that check at the moment of creation instead of lazily on the
Home tab, so a bad expense is flagged the second it's added, not just later.

The AI explanation step is the same ai.attention.explain_issues used by Needs
Attention — reused as-is, not reimplemented — with a distinct `purpose` so the
AI Usage tab can tell the two trigger points apart.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

import models
from ai.attention import explain_issues
from rules import find_issues

logger = logging.getLogger(__name__)


async def check_new_transaction(
    db: Session,
    *,
    transaction: models.Transaction,
    pot: models.Pot,
    workspace_id: int,
    user_id: int,
) -> list[str]:
    """Returns formatted warning strings to append to transaction.warnings. Never
    raises — an AI outage must not block recording the expense, same rule as the
    transaction-review call in ai/agent.py."""
    try:
        all_transactions = db.query(models.Transaction).filter_by(pot_id=pot.id).all()
        recurring_charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
        issues = find_issues([pot], all_transactions, date.today(), recurring_charges)
        # Only issues this specific transaction is responsible for, or an ongoing
        # pot-state problem it just ran into (e.g. this expense landed in an
        # already-over-budget pot) — not every unrelated issue on the pot.
        relevant = [i for i in issues if i.transaction_id in (None, transaction.id)]
        if not relevant:
            return []
        explained = await explain_issues(db, issues=relevant, workspace_id=workspace_id, user_id=user_id, purpose="rules_checker")
        return [f"{item['explanation']} Suggested fix: {item['suggested_fix']}" for item in explained]
    except Exception:
        logger.exception("Rules Checker failed for transaction on pot %s", pot.id)
        return []
