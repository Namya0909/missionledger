from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user, require_membership
from database import get_db
from settleup import compute_settle_up

router = APIRouter(prefix="/workspaces/{workspace_id}/settle-up", tags=["settle-up"])


def _require_group(workspace_id: int, db: Session) -> models.Workspace:
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if workspace.type != models.WorkspaceType.group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Settle-up only applies to groups")
    return workspace


@router.get("", response_model=schemas.SettleUpOut)
def get_settle_up(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    _require_group(workspace_id, db)

    memberships = db.query(models.Membership).filter_by(workspace_id=workspace_id).all()
    member_user_ids = [m.user_id for m in memberships]
    incomes = {m.user_id: m.monthly_income for m in memberships if m.monthly_income is not None}
    names = {m.user_id: m.user.name for m in memberships}

    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    settlements = db.query(models.Settlement).filter_by(workspace_id=workspace_id).all()

    result = compute_settle_up(pots, transactions, member_user_ids, incomes, settlements)

    return schemas.SettleUpOut(
        balances=[
            schemas.BalanceOut(user_id=uid, name=names.get(uid, "?"), amount=amount)
            for uid, amount in result.balances.items()
        ],
        transfers=[
            schemas.TransferOut(
                from_user_id=t["from_user_id"],
                from_name=names.get(t["from_user_id"], "?"),
                to_user_id=t["to_user_id"],
                to_name=names.get(t["to_user_id"], "?"),
                amount=t["amount"],
            )
            for t in result.transfers
        ],
    )


@router.get("/payments", response_model=list[schemas.SettlementOut])
def list_payments(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    _require_group(workspace_id, db)
    rows = (
        db.query(models.Settlement)
        .filter_by(workspace_id=workspace_id)
        .order_by(models.Settlement.created_at.desc())
        .all()
    )
    return [
        schemas.SettlementOut(
            id=s.id,
            from_user_id=s.from_user_id,
            from_name=s.from_user.name,
            to_user_id=s.to_user_id,
            to_name=s.to_user.name,
            amount=s.amount,
            note=s.note,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.post("/payments", response_model=schemas.SettlementOut)
def record_payment(
    workspace_id: int,
    payload: schemas.SettlementCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record a real payment YOU made to another member — you can only log money you
    sent, never claim a payment on someone else's behalf."""
    require_membership(workspace_id, current_user, db)
    _require_group(workspace_id, db)

    if payload.to_user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't record a payment to yourself")
    recipient_membership = (
        db.query(models.Membership).filter_by(workspace_id=workspace_id, user_id=payload.to_user_id).first()
    )
    if recipient_membership is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That person isn't a member of this group")

    settlement = models.Settlement(
        workspace_id=workspace_id,
        from_user_id=current_user.id,
        to_user_id=payload.to_user_id,
        amount=payload.amount,
        note=payload.note,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    log_action(
        db,
        action="settlement.recorded",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"to_user_id": payload.to_user_id, "amount": payload.amount},
    )

    return schemas.SettlementOut(
        id=settlement.id,
        from_user_id=settlement.from_user_id,
        from_name=current_user.name,
        to_user_id=settlement.to_user_id,
        to_name=recipient_membership.user.name,
        amount=settlement.amount,
        note=settlement.note,
        created_at=settlement.created_at,
    )
