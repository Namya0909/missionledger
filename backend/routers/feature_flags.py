"""Toggle the 5 cost-saving measures — same app-wide privileged gate as costs.py."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import feature_flags
import models
import schemas
from auth import get_current_user
from database import get_db
from permissions import is_privileged_anywhere

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


def _require_privileged(db: Session, current_user: models.User) -> None:
    memberships = db.query(models.Membership).filter(models.Membership.user_id == current_user.id).all()
    if not is_privileged_anywhere(memberships):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You need an admin/treasurer/owner role in at least one workspace to manage feature flags.",
        )


@router.get("", response_model=list[schemas.FeatureFlagOut])
def list_feature_flags(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    flags = feature_flags.all_flags()
    return [
        schemas.FeatureFlagOut(name=name, enabled=enabled, description=feature_flags.FLAG_DESCRIPTIONS[name])
        for name, enabled in flags.items()
    ]


@router.put("/{name}", response_model=schemas.FeatureFlagOut)
def set_feature_flag(
    name: str,
    body: schemas.FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_privileged(db, current_user)
    if name not in feature_flags.FLAG_DESCRIPTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown feature flag: {name}")
    feature_flags.set_enabled(name, body.enabled)
    return schemas.FeatureFlagOut(name=name, enabled=body.enabled, description=feature_flags.FLAG_DESCRIPTIONS[name])
