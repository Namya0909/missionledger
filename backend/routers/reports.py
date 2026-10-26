"""The Reporter: one endpoint, one button on the frontend. Python computes every
number for the workspace's type (reports.py), one AI call writes the narrative
sections (ai/reporter.py), and the whole thing is rendered to a PDF (pdf_builder.py)
and streamed back — no report is ever persisted server-side.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

import models
import pdf_builder
import reports
from ai.core import GlobalAIBudgetExceeded
from ai.reporter import generate_business_narrative, generate_group_narrative, generate_nonprofit_narrative
from auth import get_current_user, require_membership
from config import MissingAIKeyError
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces/{workspace_id}/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")

    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    recurring_charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
    today = date.today()
    pending = reports.pending_approvals(pots, transactions)

    try:
        if workspace.type == models.WorkspaceType.nonprofit:
            data = reports.nonprofit_report(pots, transactions, today)
            narrative = await generate_nonprofit_narrative(db, workspace_id=workspace_id, user_id=current_user.id, data=data)
            pdf_bytes = pdf_builder.build_nonprofit_pdf(workspace.name, data, narrative, pending)
        elif workspace.type == models.WorkspaceType.group:
            memberships = db.query(models.Membership).filter_by(workspace_id=workspace_id).all()
            member_user_ids = [m.user_id for m in memberships]
            incomes = {m.user_id: m.monthly_income for m in memberships if m.monthly_income is not None}
            names = {m.user_id: m.user.name for m in memberships}
            data = reports.group_report(pots, transactions, member_user_ids, incomes, names, today)
            narrative = await generate_group_narrative(db, workspace_id=workspace_id, user_id=current_user.id, data=data)
            pdf_bytes = pdf_builder.build_group_pdf(workspace.name, data, narrative, pending)
        else:
            data = reports.business_report(pots, transactions, recurring_charges, today)
            narrative = await generate_business_narrative(db, workspace_id=workspace_id, user_id=current_user.id, data=data)
            pdf_bytes = pdf_builder.build_business_pdf(workspace.name, data, narrative, pending)
    except MissingAIKeyError:
        raise
    except GlobalAIBudgetExceeded:
        raise
    except Exception:
        logger.exception("Report generation failed for workspace %s", workspace_id)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn't generate the report right now — try again in a moment.")

    filename = f"{workspace.name.replace(' ', '_')}_report_{today.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
