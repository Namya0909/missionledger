from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_membership
from database import get_db
from models import TransactionStatus
from routers.transactions import decide, to_out

router = APIRouter(prefix="/workspaces/{workspace_id}/approvals", tags=["approvals"])


@router.get("", response_model=list[schemas.TransactionOut])
def list_approvals(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Everything waiting in this workspace. Every pending item is included so
    anyone can see what's stuck — the frontend shows action buttons only where
    can_i_decide is true for the signed-in user."""
    require_membership(workspace_id, current_user, db)
    transactions = (
        db.query(models.Transaction)
        .filter_by(workspace_id=workspace_id, status=TransactionStatus.pending)
        .order_by(models.Transaction.date.desc())
        .all()
    )
    pots_by_id = {p.id: p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}
    return [to_out(t, pots_by_id[t.pot_id], current_user.id) for t in transactions]


@router.get("/count", response_model=int)
def count_my_approvals(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The nav badge count: how many pending items THIS user can actually act on."""
    require_membership(workspace_id, current_user, db)
    transactions = (
        db.query(models.Transaction).filter_by(workspace_id=workspace_id, status=TransactionStatus.pending).all()
    )
    pots_by_id = {p.id: p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}
    out = [to_out(t, pots_by_id[t.pot_id], current_user.id) for t in transactions]
    return sum(1 for item in out if item.can_i_decide)


class BulkDecision(BaseModel):
    transaction_ids: list[int]
    approve: bool
    reason: str | None = None


@router.post("/bulk", response_model=list[schemas.TransactionOut])
def bulk_decide(
    workspace_id: int,
    payload: BulkDecision,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Approve or reject several at once. Each one is still checked independently —
    one person not being allowed to decide an item doesn't block the rest, it's just
    skipped (reported back as an unchanged item the caller can see wasn't touched)."""
    require_membership(workspace_id, current_user, db)
    pots_by_id = {p.id: p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}

    results = []
    for transaction_id in payload.transaction_ids:
        transaction = db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
        if transaction is None:
            continue
        pot = pots_by_id.get(transaction.pot_id)
        if pot is None:
            continue
        try:
            transaction = decide(
                db,
                workspace_id=workspace_id,
                transaction=transaction,
                pot=pot,
                current_user=current_user,
                approve=payload.approve,
                reason=payload.reason,
            )
        except Exception:
            pass  # this one wasn't eligible (already decided, not an approver, etc.) — skip it
        results.append(to_out(transaction, pot, current_user.id))
    return results
