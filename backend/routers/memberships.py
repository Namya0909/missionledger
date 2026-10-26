from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user, require_membership
from database import get_db
from models import ROLES_BY_WORKSPACE_TYPE
from permissions import can_manage_members, is_sole_privileged_member
from security_log import log_security_event

router = APIRouter(prefix="/workspaces/{workspace_id}/members", tags=["members"])


def _get_workspace_or_404(workspace_id: int, db: Session) -> models.Workspace:
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace


def _require_can_manage_members(
    workspace_id: int, current_user: models.User, db: Session, *, action_detail: str
) -> tuple[models.Workspace, models.Membership]:
    workspace = _get_workspace_or_404(workspace_id, db)
    requester_membership = require_membership(workspace_id, current_user, db)
    if not can_manage_members(requester_membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail=action_detail,
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot manage members")
    return workspace, requester_membership


def _get_membership_or_404(workspace_id: int, membership_id: int, db: Session) -> models.Membership:
    membership = db.query(models.Membership).filter_by(id=membership_id, workspace_id=workspace_id).first()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return membership


@router.post("", response_model=schemas.MembershipOut)
def add_member(
    workspace_id: int,
    payload: schemas.MembershipCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace = _get_workspace_or_404(workspace_id, db)
    requester_membership = require_membership(workspace_id, current_user, db)
    if not can_manage_members(requester_membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail="Role lacks permission to add members.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add members")

    allowed_roles = ROLES_BY_WORKSPACE_TYPE[workspace.type]
    if payload.role not in allowed_roles:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Role '{payload.role.value}' is not valid for a {workspace.type.value} workspace. "
            f"Valid roles: {', '.join(r.value for r in allowed_roles)}.",
        )

    invitee = db.query(models.User).filter_by(email=payload.email.lower()).first()
    if invitee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account exists with that email yet")

    if db.query(models.Membership).filter_by(workspace_id=workspace_id, user_id=invitee.id).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That person is already a member")

    if workspace.type == models.WorkspaceType.group:
        current_count = db.query(models.Membership).filter_by(workspace_id=workspace_id).count()
        if current_count >= models.GROUP_MAX_MEMBERS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"A group can have at most {models.GROUP_MAX_MEMBERS} people"
            )

    membership = models.Membership(
        user_id=invitee.id, workspace_id=workspace_id, role=payload.role, monthly_income=payload.monthly_income
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    log_action(
        db,
        action="member.added",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"added_user_email": invitee.email, "role": payload.role.value},
    )
    return membership


@router.get("", response_model=list[schemas.MembershipOut])
def list_members(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    return db.query(models.Membership).filter_by(workspace_id=workspace_id).all()


@router.put("/{membership_id}/income", response_model=schemas.MembershipOut)
def set_income(
    workspace_id: int,
    membership_id: int,
    payload: schemas.IncomeUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Needed for a group's "split by income" pots. Only an admin/treasurer/owner
    sets this for now, to keep it consistent with who manages the group's setup."""
    workspace = _get_workspace_or_404(workspace_id, db)
    requester_membership = require_membership(workspace_id, current_user, db)
    if not can_manage_members(requester_membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail="Role lacks permission to set income.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot set income")

    membership = db.query(models.Membership).filter_by(id=membership_id, workspace_id=workspace_id).first()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    membership.monthly_income = payload.monthly_income
    db.commit()
    db.refresh(membership)
    return membership


@router.put("/{membership_id}/role", response_model=schemas.MembershipOut)
def update_member_role(
    workspace_id: int,
    membership_id: int,
    payload: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, _ = _require_can_manage_members(
        workspace_id, current_user, db, action_detail="Role lacks permission to change a member's role."
    )
    membership = _get_membership_or_404(workspace_id, membership_id, db)

    allowed_roles = ROLES_BY_WORKSPACE_TYPE[workspace.type]
    if payload.role not in allowed_roles:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Role '{payload.role.value}' is not valid for a {workspace.type.value} workspace. "
            f"Valid roles: {', '.join(r.value for r in allowed_roles)}.",
        )

    if membership.role != payload.role and is_sole_privileged_member(membership, db):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This is the only member who can manage pots, members, and the security log here — "
            "give someone else that role first.",
        )

    old_role = membership.role
    membership.role = payload.role
    db.commit()
    db.refresh(membership)

    log_action(
        db,
        action="member.role_changed",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"user_email": membership.user.email, "old_role": old_role.value, "new_role": payload.role.value},
    )
    return membership


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, _ = _require_can_manage_members(
        workspace_id, current_user, db, action_detail="Role lacks permission to remove a member."
    )
    membership = _get_membership_or_404(workspace_id, membership_id, db)

    if is_sole_privileged_member(membership, db):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This is the only member who can manage pots, members, and the security log here — "
            "give someone else that role before removing them.",
        )
    if workspace.type == models.WorkspaceType.group:
        remaining = db.query(models.Membership).filter_by(workspace_id=workspace_id).count() - 1
        if remaining < models.GROUP_MIN_MEMBERS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"A group needs at least {models.GROUP_MIN_MEMBERS} people"
            )

    removed_email = membership.user.email
    removed_role = membership.role

    # Prune them from any pot's approver list so a pending transaction never ends
    # up stuck forever waiting on someone who's no longer in the workspace.
    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    for pot in pots:
        if pot.approver_user_ids and membership.user_id in pot.approver_user_ids:
            pot.approver_user_ids = [uid for uid in pot.approver_user_ids if uid != membership.user_id]

    db.delete(membership)
    db.commit()

    log_action(
        db,
        action="member.removed",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"removed_user_email": removed_email, "role": removed_role.value},
    )
