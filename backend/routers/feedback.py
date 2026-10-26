"""App-wide feedback — submittable from any page (workspace_id optional), and a
privileged-anywhere-gated averages/list view, same pattern as routers/costs.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import feedback_stats
import models
import schemas
from auth import get_current_user, require_membership
from database import get_db
from permissions import is_privileged_anywhere

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _require_privileged(db: Session, current_user: models.User) -> None:
    memberships = db.query(models.Membership).filter(models.Membership.user_id == current_user.id).all()
    if not is_privileged_anywhere(memberships):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You need an admin/treasurer/owner role in at least one workspace to view feedback.",
        )


@router.post("", response_model=schemas.FeedbackOut)
def submit_feedback(
    payload: schemas.FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.workspace_id is not None:
        require_membership(payload.workspace_id, current_user, db)
    feedback = models.Feedback(
        user_id=current_user.id,
        workspace_id=payload.workspace_id,
        message=payload.message,
        rating=payload.rating,
        minutes_before=payload.minutes_before,
        minutes_with=payload.minutes_with,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("", response_model=list[schemas.FeedbackOut])
def list_feedback(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    return feedback_stats.raw_rows(db)


@router.get("/summary", response_model=schemas.FeedbackSummaryOut)
def get_feedback_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    summary = feedback_stats.compute_summary(db)
    return schemas.FeedbackSummaryOut(
        response_count=summary.response_count,
        avg_rating=summary.avg_rating,
        avg_minutes_before=summary.avg_minutes_before,
        avg_minutes_with=summary.avg_minutes_with,
        avg_minutes_saved=summary.avg_minutes_saved,
    )
