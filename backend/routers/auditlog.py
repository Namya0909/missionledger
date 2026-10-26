from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_membership
from database import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}/audit-log", tags=["audit-log"])


@router.get("", response_model=list[schemas.AuditLogOut])
def list_audit_log(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Every member can see this workspace's history — nothing in it is more
    sensitive than what's already visible elsewhere (pot names, who did what)."""
    require_membership(workspace_id, current_user, db)
    rows = (
        db.query(models.AuditLogEntry)
        .filter_by(workspace_id=workspace_id)
        .order_by(models.AuditLogEntry.created_at.desc())
        .limit(300)
        .all()
    )
    return [
        schemas.AuditLogOut(
            id=r.id,
            action=r.action,
            details=r.details,
            user_name=db.get(models.User, r.user_id).name if r.user_id else None,
            created_at=r.created_at,
        )
        for r in rows
    ]
