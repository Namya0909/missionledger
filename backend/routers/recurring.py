from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user, require_membership
from database import get_db
from permissions import can_create_transaction, can_manage_pots
from recurring import generate_due_charges

router = APIRouter(prefix="/workspaces/{workspace_id}/recurring", tags=["recurring"])


def _to_out(charge: models.RecurringCharge) -> schemas.RecurringChargeOut:
    return schemas.RecurringChargeOut(
        id=charge.id,
        pot_id=charge.pot_id,
        pot_name=charge.pot.name,
        merchant=charge.merchant,
        amount=charge.amount,
        category=charge.category,
        day_of_month=charge.day_of_month,
        active=charge.active,
        created_by_name=charge.created_by.name,
        created_at=charge.created_at,
    )


@router.get("", response_model=list[schemas.RecurringChargeOut])
def list_recurring(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    # Catch up on anything due before showing the list, so a long-idle app doesn't
    # silently fall behind on bills.
    generate_due_charges(db, workspace_id)
    charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
    return [_to_out(c) for c in charges]


@router.post("", response_model=schemas.RecurringChargeOut)
def create_recurring(
    workspace_id: int,
    payload: schemas.RecurringChargeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Anyone who can add an expense by hand can also set up a recurring one —
    it just saves them re-typing the same bill every month."""
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if not can_create_transaction(membership, workspace.type):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add expenses")

    pot = db.query(models.Pot).filter_by(id=payload.pot_id, workspace_id=workspace_id).first()
    if pot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pot not found")

    charge = models.RecurringCharge(
        workspace_id=workspace_id,
        pot_id=payload.pot_id,
        merchant=payload.merchant,
        amount=payload.amount,
        category=payload.category,
        day_of_month=payload.day_of_month,
        created_by_user_id=current_user.id,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)

    log_action(
        db,
        action="recurring.created",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"merchant": charge.merchant, "amount": charge.amount, "day_of_month": charge.day_of_month},
    )
    return _to_out(charge)


@router.delete("/{charge_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_recurring(
    workspace_id: int,
    charge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    charge = db.query(models.RecurringCharge).filter_by(id=charge_id, workspace_id=workspace_id).first()
    if charge is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurring charge not found")
    workspace = db.get(models.Workspace, workspace_id)
    if charge.created_by_user_id != current_user.id and not can_manage_pots(membership, workspace.type):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only whoever set this up, or a pot manager, can remove it")
    charge.active = False
    db.commit()
    log_action(
        db,
        action="recurring.deactivated",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"charge_id": charge_id, "merchant": charge.merchant},
    )
