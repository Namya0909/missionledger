from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user, require_membership
from database import get_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# The role a workspace's creator gets automatically — must be a role with
# manage_pots/manage_members (see permissions.py), or a brand-new workspace would
# have no one able to set it up.
DEFAULT_CREATOR_ROLE: dict[models.WorkspaceType, models.Role] = {
    models.WorkspaceType.group: models.Role.admin,
    models.WorkspaceType.nonprofit: models.Role.treasurer,
    models.WorkspaceType.business: models.Role.owner,
}


def _to_out(db: Session, workspace: models.Workspace, role: models.Role) -> schemas.WorkspaceOut:
    count = db.query(models.Membership).filter_by(workspace_id=workspace.id).count()
    return schemas.WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        type=workspace.type,
        status=workspace.status,
        is_couple=workspace.is_couple,
        tax_pack_enabled=workspace.tax_pack_enabled,
        state=workspace.state,
        member_count=count,
        role=role,
        created_at=workspace.created_at,
    )


@router.post("", response_model=schemas.WorkspaceOut)
def create_workspace(
    payload: schemas.WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace = models.Workspace(
        name=payload.name,
        type=payload.type,
        tax_pack_enabled=payload.tax_pack_enabled,
        state=(payload.state or "").upper() or None,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    role = DEFAULT_CREATOR_ROLE[payload.type]
    db.add(
        models.Membership(
            user_id=current_user.id,
            workspace_id=workspace.id,
            role=role,
        )
    )
    db.commit()

    log_action(
        db,
        action="workspace.created",
        workspace_id=workspace.id,
        user_id=current_user.id,
        details={"name": workspace.name, "type": workspace.type.value},
    )
    return _to_out(db, workspace, role)


@router.get("", response_model=list[schemas.WorkspaceOut])
def list_my_workspaces(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    memberships = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == current_user.id)
        .all()
    )
    return [_to_out(db, m.workspace, m.role) for m in memberships]


@router.get("/{workspace_id}", response_model=schemas.WorkspaceOut)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return _to_out(db, workspace, membership.role)


@router.put("/{workspace_id}/couple", response_model=schemas.WorkspaceOut)
def set_couple_status(
    workspace_id: int,
    payload: schemas.CoupleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Optional, never required: lets either of a 2-person group confirm they're a
    couple so the UI can show a heart icon instead of generic group framing."""
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    member_count = db.query(models.Membership).filter_by(workspace_id=workspace_id).count()
    if workspace.type != models.WorkspaceType.group or member_count != 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a 2-person group can set couple status")

    workspace.is_couple = payload.is_couple
    db.commit()
    return _to_out(db, workspace, membership.role)


@router.put("/{workspace_id}/tax-pack", response_model=schemas.WorkspaceOut)
def set_tax_pack_enabled(
    workspace_id: int,
    payload: schemas.TaxPackEnabledUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Opt in/out of the Tax Prep Pack anytime after signup — restricted to whoever
    manages members (same trust tier as every other workspace-wide setting)."""
    from permissions import can_manage_members

    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if not can_manage_members(membership, workspace.type):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to change this setting.")

    workspace.tax_pack_enabled = payload.enabled
    db.commit()
    log_action(
        db,
        action="tax_pack.toggled",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"enabled": payload.enabled},
    )
    return _to_out(db, workspace, membership.role)
