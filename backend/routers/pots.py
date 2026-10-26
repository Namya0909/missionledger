from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user, require_membership
from database import get_db
from permissions import can_manage_pots
from rules import pot_usage
from security_log import log_security_event

router = APIRouter(prefix="/workspaces/{workspace_id}/pots", tags=["pots"])


def _validate_approvers(db: Session, workspace_id: int, user_ids: list[int]) -> None:
    member_user_ids = {
        m.user_id for m in db.query(models.Membership).filter_by(workspace_id=workspace_id).all()
    }
    bad = [uid for uid in user_ids if uid not in member_user_ids]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Not a member of this workspace: {bad}")


def _to_out(pot: models.Pot, transactions: list[models.Transaction]) -> schemas.PotOut:
    usage = pot_usage(pot, transactions, date.today())
    return schemas.PotOut(
        **{c.name: getattr(pot, c.name) for c in models.Pot.__table__.columns},
        period=usage.period,
        period_used=usage.used,
        period_limit=usage.limit,
        period_pct=usage.pct,
        status=usage.status,
    )


@router.post("", response_model=schemas.PotOut)
def create_pot(
    workspace_id: int,
    payload: schemas.PotCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if not can_manage_pots(membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail="Role lacks permission to create pots.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot create pots")

    starting_balance = (
        0.0 if payload.type in models.DEPOSIT_POT_TYPES else (payload.budget_or_grant_amount or 0.0)
    )
    if payload.approver_user_ids:
        _validate_approvers(db, workspace_id, payload.approver_user_ids)

    pot = models.Pot(workspace_id=workspace_id, current_balance=starting_balance, **payload.model_dump())
    db.add(pot)
    db.commit()
    db.refresh(pot)

    log_action(
        db,
        action="pot.created",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={
            "name": pot.name,
            "type": pot.type.value,
            "approval_required": pot.approval_required,
            "approval_threshold": pot.approval_threshold,
            "approver_user_ids": pot.approver_user_ids,
        },
    )
    return _to_out(pot, [])


@router.get("", response_model=list[schemas.PotOut])
def list_pots(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    return [_to_out(pot, transactions) for pot in pots]


@router.get("/{pot_id}", response_model=schemas.PotOut)
def get_pot(
    workspace_id: int,
    pot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    pot = db.query(models.Pot).filter_by(id=pot_id, workspace_id=workspace_id).first()
    if pot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pot not found")
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id, pot_id=pot_id).all()
    return _to_out(pot, transactions)


@router.put("/{pot_id}/approval", response_model=schemas.PotOut)
def update_approval_settings(
    workspace_id: int,
    pot_id: int,
    payload: schemas.PotApprovalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The approval toggle, threshold, and approver list — only a treasurer, owner,
    or group admin (manage_pots) can change these. Every change is logged."""
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if not can_manage_pots(membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail="Role lacks permission to change approval settings.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot change approval settings")

    pot = db.query(models.Pot).filter_by(id=pot_id, workspace_id=workspace_id).first()
    if pot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pot not found")

    if payload.approval_required and not payload.approver_user_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose at least one approver to turn approval on")
    if payload.approver_user_ids:
        _validate_approvers(db, workspace_id, payload.approver_user_ids)

    before = {
        "approval_required": pot.approval_required,
        "approval_threshold": pot.approval_threshold,
        "approver_user_ids": pot.approver_user_ids,
    }
    pot.approval_required = payload.approval_required
    pot.approval_threshold = payload.approval_threshold
    pot.approver_user_ids = payload.approver_user_ids or None
    db.commit()
    db.refresh(pot)

    log_action(
        db,
        action="pot.approval_settings_changed",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"pot_id": pot.id, "pot_name": pot.name, "before": before, "after": payload.model_dump()},
    )

    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id, pot_id=pot_id).all()
    return _to_out(pot, transactions)
