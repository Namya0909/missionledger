from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

import models
import schemas
from ai.setup_agent import finalize_workspace_from_plan, generate_plan, run_setup_turn
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/setup", tags=["setup"])


@router.post("/message", response_model=schemas.SetupResponse)
async def setup_message(
    payload: schemas.SetupMessage,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    history = [h.model_dump() for h in payload.history]
    turn, question_number, turn_error = await run_setup_turn(
        db, user_id=current_user.id, history=history, message=payload.message
    )

    if turn_error:
        return schemas.SetupResponse(reply="", declined=False, done=False, question_number=question_number, error=turn_error)

    if not turn.in_scope:
        return schemas.SetupResponse(
            reply=turn.decline_reason or "I can only help set up a budgeting workspace.",
            declined=True,
            done=True,
            question_number=0,
        )

    if turn.ready_to_create and turn.workspace_type:
        plan, plan_error = await generate_plan(
            db, user_id=current_user.id, workspace_type=turn.workspace_type, collected=turn.collected
        )
        if plan_error:
            return schemas.SetupResponse(
                reply=turn.reply, declined=False, done=False, question_number=question_number, error=plan_error
            )
        return schemas.SetupResponse(
            reply=turn.reply, declined=False, done=True, question_number=question_number, plan=plan
        )

    return schemas.SetupResponse(reply=turn.reply, declined=False, done=False, question_number=question_number)


@router.post("/create", response_model=schemas.CreateFromPlanResponse)
def create_from_plan(
    payload: schemas.CreateFromPlanRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Nothing before this point touched the database — this is the only write."""
    workspace, invite_links = finalize_workspace_from_plan(
        db,
        user=current_user,
        workspace_type=payload.workspace_type.value,
        suggested_name=payload.suggested_name,
        pots=payload.pots,
        invites=payload.invites,
        tax_pack_enabled=payload.tax_pack_enabled,
        state=payload.state,
    )
    base_url = str(request.base_url).rstrip("/")
    return schemas.CreateFromPlanResponse(
        workspace_id=workspace.id,
        invite_links=[
            schemas.InviteLinkOut(role=link.role, label=link.label, token=link.token, url=f"{base_url}/join/{link.token}")
            for link in invite_links
        ],
    )
