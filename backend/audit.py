from sqlalchemy.orm import Session

import models


def log_action(
    db: Session,
    *,
    action: str,
    workspace_id: int | None = None,
    user_id: int | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        models.AuditLogEntry(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            details=details,
        )
    )
    db.commit()
