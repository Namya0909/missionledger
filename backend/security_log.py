"""The Security Log: every time a defense actually does something (blocks,
redacts, throttles, locks), it gets recorded here — this is what the
Security Log page and the attack test suite both check against, instead of
just trusting that a defense "should" have worked.
"""

from sqlalchemy.orm import Session

import models


def log_security_event(
    db: Session,
    *,
    defense: str,
    action: str,
    detail: str,
    workspace_id: int | None = None,
    user_id: int | None = None,
) -> None:
    db.add(
        models.SecurityLogEntry(
            workspace_id=workspace_id,
            user_id=user_id,
            defense=defense,
            action=action,
            detail=detail,
        )
    )
    db.commit()
