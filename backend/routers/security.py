from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_membership
from database import get_db
from permissions import Capability, has_capability

router = APIRouter(prefix="/workspaces/{workspace_id}/security-log", tags=["security"])


@router.get("", response_model=list[schemas.SecurityLogOut])
def list_security_log(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if not has_capability(workspace.type, membership.role, Capability.view_security_log):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot view the security log")

    # Workspace-scoped events (chat blocks, PII redactions, rate limits, upload
    # rejections) plus this viewer's OWN account-level events (login lockout —
    # which happens before any workspace context exists, so it has no natural
    # workspace home under the per-workspace-admin model this app uses).
    entries = (
        db.query(models.SecurityLogEntry)
        .filter(
            or_(
                models.SecurityLogEntry.workspace_id == workspace_id,
                (models.SecurityLogEntry.workspace_id.is_(None))
                & (models.SecurityLogEntry.user_id == current_user.id),
            )
        )
        .order_by(models.SecurityLogEntry.created_at.desc())
        .all()
    )

    users_by_id = {u.id: u for u in db.query(models.User).all()}
    return [
        schemas.SecurityLogOut(
            id=e.id,
            defense=e.defense,
            action=e.action,
            detail=e.detail,
            user_name=users_by_id[e.user_id].name if e.user_id in users_by_id else None,
            created_at=e.created_at,
        )
        for e in entries
    ]
