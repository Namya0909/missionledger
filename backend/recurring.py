"""Generates a real Transaction from each active RecurringCharge once it's due each
month — the same way a person adding it by hand would, including going through the
pot's own approval rules. Pure Python, runs idempotently (safe to call often): a
charge already generated for the current month is skipped.
"""

import calendar
from datetime import date

from sqlalchemy.orm import Session

import models
from permissions import needs_approval


def _due_date_for(charge: models.RecurringCharge, today: date) -> date:
    last_day = calendar.monthrange(today.year, today.month)[1]
    day = min(charge.day_of_month, last_day)
    return date(today.year, today.month, day)


def generate_due_charges(db: Session, workspace_id: int | None = None) -> list[models.Transaction]:
    """Checks every active recurring charge (optionally scoped to one workspace) and
    creates this month's transaction for any that are due and haven't fired yet."""
    today = date.today()
    query = db.query(models.RecurringCharge).filter_by(active=True)
    if workspace_id is not None:
        query = query.filter_by(workspace_id=workspace_id)

    created: list[models.Transaction] = []
    for charge in query.all():
        if charge.last_generated_year == today.year and charge.last_generated_month == today.month:
            continue
        due_date = _due_date_for(charge, today)
        if today < due_date:
            continue

        pot = db.get(models.Pot, charge.pot_id)
        if pot is None:
            continue

        requires = needs_approval(pot, charge.amount)
        transaction = models.Transaction(
            workspace_id=charge.workspace_id,
            pot_id=pot.id,
            date=due_date,
            merchant=charge.merchant,
            amount=charge.amount,
            category=charge.category,
            status=models.TransactionStatus.pending if requires else models.TransactionStatus.approved,
            source=models.TransactionSource.typed,
            warnings=[],
            created_by_user_id=charge.created_by_user_id,
        )
        db.add(transaction)
        if not requires:
            if pot.type in models.DEPOSIT_POT_TYPES:
                pot.current_balance += transaction.amount
            else:
                pot.current_balance -= transaction.amount

        charge.last_generated_year = today.year
        charge.last_generated_month = today.month
        created.append(transaction)

    if created:
        db.commit()
    return created
