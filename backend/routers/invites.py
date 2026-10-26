from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from audit import log_action
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/invite", tags=["invites"])


def _get_active_link_or_404(token: str, db: Session) -> models.InviteLink:
    link = db.query(models.InviteLink).filter_by(token=token, active=True).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite link is invalid or no longer active")
    return link


@router.get("/{token}", response_model=schemas.InvitePreviewOut)
def preview_invite(token: str, db: Session = Depends(get_db)):
    """Public — no login needed, so a brand-new person can see what they're being
    invited to before signing up."""
    link = _get_active_link_or_404(token, db)
    return schemas.InvitePreviewOut(
        workspace_name=link.workspace.name, workspace_type=link.workspace.type, role=link.role, label=link.label
    )


@router.post("/{token}/accept", response_model=schemas.InviteAcceptResponse)
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    link = _get_active_link_or_404(token, db)
    existing = (
        db.query(models.Membership).filter_by(workspace_id=link.workspace_id, user_id=current_user.id).first()
    )
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You're already a member of this workspace")

    if link.workspace.type == models.WorkspaceType.group:
        count = db.query(models.Membership).filter_by(workspace_id=link.workspace_id).count()
        if count >= models.GROUP_MAX_MEMBERS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This group is already at the {models.GROUP_MAX_MEMBERS}-person limit")

    db.add(models.Membership(user_id=current_user.id, workspace_id=link.workspace_id, role=link.role))
    db.commit()

    log_action(
        db, action="member.joined_via_invite", workspace_id=link.workspace_id, user_id=current_user.id,
        details={"role": link.role.value},
    )
    return schemas.InviteAcceptResponse(workspace_id=link.workspace_id, workspace_name=link.workspace.name)
