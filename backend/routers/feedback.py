"""App-wide feedback — submittable from any page (workspace_id optional), but
viewable ONLY by the single designated owner account (config.FEEDBACK_ADMIN_EMAIL)
— deliberately NOT every workspace admin/treasurer/owner (routers/costs.py's
pattern), since on the live site that's effectively anyone who signs up: every new
user becomes an admin of their own brand-new workspace immediately.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
import feedback_stats
from auth import get_current_user, require_membership
from database import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _require_feedback_admin(current_user: models.User) -> None:
    if not current_user.is_feedback_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can view feedback.")


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
        reviewer_role=payload.reviewer_role,
        structured_answers=payload.structured_answers,
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
    _require_feedback_admin(current_user)
    return feedback_stats.raw_rows(db)


@router.get("/summary", response_model=schemas.FeedbackSummaryOut)
def get_feedback_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_feedback_admin(current_user)
    summary = feedback_stats.compute_summary(db)
    return schemas.FeedbackSummaryOut(
        response_count=summary.response_count,
        avg_rating=summary.avg_rating,
        avg_minutes_before=summary.avg_minutes_before,
        avg_minutes_with=summary.avg_minutes_with,
        avg_minutes_saved=summary.avg_minutes_saved,
        by_role=summary.by_role,
    )
