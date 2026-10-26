import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from ai.core import GlobalAIBudgetExceeded
from ai.orchestrator import handle_chat_request
from auth import get_current_user, require_membership
from config import MissingAIKeyError
from database import get_db
from ratelimit import check_sliding_window
from security_log import log_security_event

router = APIRouter(prefix="/workspaces/{workspace_id}/chat", tags=["chat"])
logger = logging.getLogger(__name__)

SAFE_FALLBACK_REPLY = (
    "I couldn't process that message safely, so I'm not going to answer it. "
    "Try rephrasing your question about this workspace's budget."
)

CHAT_RATE_LIMIT = 20
CHAT_RATE_WINDOW_SECONDS = 60


@router.post("", response_model=schemas.ChatResponse)
async def chat(
    workspace_id: int,
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)

    if not check_sliding_window(f"chat:{current_user.id}", limit=CHAT_RATE_LIMIT, window_seconds=CHAT_RATE_WINDOW_SECONDS):
        log_security_event(
            db, defense="Rate Limiting", action="throttled",
            detail=f"Chat throttled: more than {CHAT_RATE_LIMIT} messages in a minute.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You're sending messages too quickly — please wait a moment and try again.",
        )

    # The AI provider itself (not just our Gatekeeper) can refuse a request outright —
    # e.g. a content filter rejecting an adversarial prompt before a completion is even
    # returned. Either way, the user must see a safe message, never the provider's raw
    # error (which can include internal URLs/details).
    try:
        reply, blocked, trace, cost = await handle_chat_request(
            db, workspace_id=workspace_id, user_id=current_user.id, message=payload.message
        )
    except MissingAIKeyError:
        raise
    except GlobalAIBudgetExceeded as exc:
        # Chat always returns 200 with a chat-bubble-shaped reply, even when
        # blocked — a raw 503 here would look like the whole app broke, not just
        # that today's shared AI budget ran out.
        return schemas.ChatResponse(reply=str(exc), blocked=True)
    except Exception:
        logger.exception("Orchestrator call failed for workspace %s", workspace_id)
        return schemas.ChatResponse(reply=SAFE_FALLBACK_REPLY, blocked=True)

    return schemas.ChatResponse(
        reply=reply,
        blocked=blocked,
        trace=[step.model_dump() for step in trace],
        total_input_tokens=cost.input_tokens,
        total_cached_tokens=cost.cached_tokens,
        total_output_tokens=cost.output_tokens,
        total_cost_usd=cost.cost_usd,
    )
