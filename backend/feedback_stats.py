"""Pure-Python averages over Feedback rows — same "Python computes" rule as
costs.py. Averages are computed only over responses that actually answered
that particular field, not by treating a blank answer as zero.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

import models


@dataclass
class FeedbackSummary:
    response_count: int = 0
    avg_rating: float | None = None
    avg_minutes_before: float | None = None
    avg_minutes_with: float | None = None
    avg_minutes_saved: float | None = None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def compute_summary(db: Session) -> FeedbackSummary:
    rows = db.query(models.Feedback).all()
    if not rows:
        return FeedbackSummary()

    ratings = [r.rating for r in rows if r.rating is not None]
    before = [r.minutes_before for r in rows if r.minutes_before is not None]
    with_ = [r.minutes_with for r in rows if r.minutes_with is not None]
    saved = [r.minutes_before - r.minutes_with for r in rows if r.minutes_before is not None and r.minutes_with is not None]

    return FeedbackSummary(
        response_count=len(rows),
        avg_rating=_avg(ratings),
        avg_minutes_before=_avg(before),
        avg_minutes_with=_avg(with_),
        avg_minutes_saved=_avg(saved),
    )


def raw_rows(db: Session) -> list[models.Feedback]:
    return db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()
