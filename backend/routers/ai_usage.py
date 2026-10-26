from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_membership
from database import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}/ai-usage", tags=["ai-usage"])


@router.get("", response_model=list[schemas.AIUsageOut])
def list_ai_usage(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    return (
        db.query(models.AIUsageLog)
        .filter_by(workspace_id=workspace_id)
        .order_by(models.AIUsageLog.created_at.desc())
        .all()
    )
