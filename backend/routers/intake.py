"""Intake: reads a bank/credit-card statement CSV, a receipt photo, or a grant
agreement PDF and stages what it found for a human to check. Nothing from any of
these three endpoints is saved — they only return data for a review table. The
two confirm endpoints are plain Python (no AI call, no agent tool) that create the
real, human-approved rows, exactly like the Setup Agent's plan -> create step.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

import models
import schemas
from ai.intake import (
    GrantParseError,
    StatementParseError,
    VisionUnavailableError,
    classify_statement_rows,
    parse_grant_pdf,
    parse_statement_csv,
    read_receipt_image,
)
from ai.rules_checker import check_new_transaction
from audit import log_action
from auth import get_current_user, require_membership
from config import MissingAIKeyError
from database import get_db
from file_validation import sniff_matches_declared_type
from models import TransactionStatus
from permissions import can_create_transaction, can_manage_pots
from routers.pots import _to_out
from security_log import log_security_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces/{workspace_id}/intake", tags=["intake"])

# App-wide upload policy: CSV, PNG, JPG, or PDF only, 5 MB max.
ALLOWED_RECEIPT_TYPES = {"image/jpeg": "image/jpeg", "image/png": "image/png"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _deny(db: Session, *, workspace_id: int, user_id: int, action_label: str) -> None:
    log_security_event(
        db, defense="Access Control", action="blocked",
        detail=f"Role lacks permission to {action_label}.",
        workspace_id=workspace_id, user_id=user_id,
    )


def _log_pii_if_any(db: Session, counts: dict[str, int], *, workspace_id: int, user_id: int, source: str) -> None:
    if not counts:
        return
    summary = ", ".join(f"{n} {label}" for label, n in counts.items())
    log_security_event(
        db,
        defense="PII Redaction",
        action="redacted",
        detail=f"Redacted {summary} from {source} before sending it to the AI.",
        workspace_id=workspace_id,
        user_id=user_id,
    )


def _get_workspace_and_membership(workspace_id: int, current_user: models.User, db: Session):
    membership = require_membership(workspace_id, current_user, db)
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace, membership


@router.post("/statement", response_model=schemas.IntakeStatementResponse)
async def upload_statement(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, membership = _get_workspace_and_membership(workspace_id, current_user, db)
    if not can_create_transaction(membership, workspace.type):
        _deny(db, workspace_id=workspace_id, user_id=current_user.id, action_label="add expenses")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add expenses")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Statement upload rejected: {len(contents)} bytes exceeds the 5 MB limit.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is too large (max 5 MB)")
    try:
        rows, pii_counts = parse_statement_csv(contents)
        _log_pii_if_any(db, pii_counts, workspace_id=workspace_id, user_id=current_user.id, source="the uploaded statement")
    except StatementParseError as exc:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Statement upload rejected: {exc}", workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        classified = await classify_statement_rows(db, workspace_id=workspace_id, user_id=current_user.id, rows=rows)
    except MissingAIKeyError:
        raise
    except Exception:
        logger.exception("Statement classification failed for workspace %s", workspace_id)
        classified = [
            {
                "date": r.date.isoformat(),
                "merchant": r.merchant,
                "amount": r.amount,
                "suggested_pot": "Unmatched",
                "suggested_category": "Uncategorized",
            }
            for r in rows
        ]

    log_action(
        db, action="intake.statement_uploaded", workspace_id=workspace_id, user_id=current_user.id,
        details={"filename": file.filename, "row_count": len(classified)},
    )
    return schemas.IntakeStatementResponse(rows=classified)


@router.post("/receipt", response_model=schemas.IntakeReceiptResponse)
async def upload_receipt(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, membership = _get_workspace_and_membership(workspace_id, current_user, db)
    if not can_create_transaction(membership, workspace.type):
        _deny(db, workspace_id=workspace_id, user_id=current_user.id, action_label="add expenses")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add expenses")

    if file.content_type not in ALLOWED_RECEIPT_TYPES:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: content type '{file.content_type}' is not PNG or JPG.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Receipts must be a PNG or JPG image")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: {len(contents)} bytes exceeds the 5 MB limit.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is too large (max 5 MB)")
    if not sniff_matches_declared_type(contents, file.content_type):
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: file content doesn't match its claimed type '{file.content_type}'.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This file doesn't look like a real PNG or JPG image")

    try:
        extraction, pii_counts = await read_receipt_image(
            db, workspace_id=workspace_id, user_id=current_user.id, image_bytes=contents, media_type=file.content_type
        )
        _log_pii_if_any(db, pii_counts, workspace_id=workspace_id, user_id=current_user.id, source="the receipt")
    except VisionUnavailableError:
        log_action(db, action="intake.receipt_vision_unavailable", workspace_id=workspace_id, user_id=current_user.id)
        return schemas.IntakeReceiptResponse(
            vision_available=False,
            message="This AI model can't read images — please type in the store, date, amount, items, and category yourself.",
        )
    except MissingAIKeyError:
        raise
    except Exception:
        logger.exception("Receipt extraction failed for workspace %s", workspace_id)
        return schemas.IntakeReceiptResponse(
            vision_available=False,
            message="Something went wrong reading this receipt — please type in the details yourself.",
        )

    log_action(db, action="intake.receipt_uploaded", workspace_id=workspace_id, user_id=current_user.id, details={"filename": file.filename})
    return schemas.IntakeReceiptResponse(
        vision_available=True,
        store=extraction.store,
        date=extraction.date,
        amount=extraction.amount,
        items=extraction.items,
        suggested_category=extraction.suggested_category,
        suggested_pot=extraction.suggested_pot,
    )


@router.post("/grant", response_model=schemas.IntakeGrantResponse)
async def upload_grant(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, membership = _get_workspace_and_membership(workspace_id, current_user, db)
    if not can_manage_pots(membership, workspace.type):
        _deny(db, workspace_id=workspace_id, user_id=current_user.id, action_label="create pots")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot create pots")

    if file.content_type != "application/pdf":
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Grant upload rejected: content type '{file.content_type}' is not PDF.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Grant agreements must be uploaded as a PDF")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Grant upload rejected: {len(contents)} bytes exceeds the 5 MB limit.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is too large (max 5 MB)")
    if not sniff_matches_declared_type(contents, file.content_type):
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Grant upload rejected: file content doesn't match its claimed type '{file.content_type}'.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This file doesn't look like a real PDF")

    try:
        extraction, pii_counts = await parse_grant_pdf(db, workspace_id=workspace_id, user_id=current_user.id, pdf_bytes=contents)
        _log_pii_if_any(db, pii_counts, workspace_id=workspace_id, user_id=current_user.id, source="the grant agreement")
    except GrantParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except MissingAIKeyError:
        raise
    except Exception:
        logger.exception("Grant PDF parsing failed for workspace %s", workspace_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Couldn't read this grant agreement right now — try again, or enter the pot by hand.",
        )

    log_action(db, action="intake.grant_uploaded", workspace_id=workspace_id, user_id=current_user.id, details={"filename": file.filename})
    return schemas.IntakeGrantResponse(
        grant_name=extraction.grant_name,
        grantor=extraction.grantor,
        amount=extraction.amount,
        start_date=extraction.start_date,
        end_date=extraction.end_date,
        allowed_categories=extraction.allowed_categories,
        disallowed_categories=extraction.disallowed_categories,
        report_deadlines=[{"date": d.date, "description": d.description} for d in extraction.report_deadlines],
    )


@router.post("/confirm-transactions", response_model=list[schemas.TransactionOut])
async def confirm_transactions(
    workspace_id: int,
    payload: schemas.ConfirmIntakeTransactionsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    from routers.transactions import to_out

    workspace, membership = _get_workspace_and_membership(workspace_id, current_user, db)
    if not can_create_transaction(membership, workspace.type):
        _deny(db, workspace_id=workspace_id, user_id=current_user.id, action_label="add expenses")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add expenses")

    pots_by_name = {p.name.lower(): p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}
    created = []
    for row in payload.rows:
        pot = pots_by_name.get(row.pot_name.lower())
        if pot is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No pot named '{row.pot_name}' in this workspace")

        # An Intake-sourced row always starts pending — machine-read data gets a
        # mandatory human check regardless of the pot's own approval toggle.
        transaction = models.Transaction(
            workspace_id=workspace_id,
            pot_id=pot.id,
            date=row.date,
            merchant=row.merchant,
            description=row.description,
            amount=row.amount,
            category=row.category,
            source=row.source,
            warnings=[],
            status=TransactionStatus.pending,
            created_by_user_id=current_user.id,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        rules_warnings = await check_new_transaction(
            db, transaction=transaction, pot=pot, workspace_id=workspace_id, user_id=current_user.id
        )
        if rules_warnings:
            transaction.warnings = rules_warnings
            db.commit()
            db.refresh(transaction)

        created.append(to_out(transaction, pot, current_user.id))

    log_action(
        db, action="intake.transactions_confirmed", workspace_id=workspace_id, user_id=current_user.id,
        details={"count": len(created)},
    )
    return created


@router.post("/confirm-grant", response_model=schemas.PotOut)
def confirm_grant(
    workspace_id: int,
    payload: schemas.ConfirmIntakeGrantRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workspace, membership = _get_workspace_and_membership(workspace_id, current_user, db)
    if not can_manage_pots(membership, workspace.type):
        _deny(db, workspace_id=workspace_id, user_id=current_user.id, action_label="create pots")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot create pots")

    pot = models.Pot(
        workspace_id=workspace_id,
        name=payload.pot_name,
        type=models.PotType.restricted_grant,
        budget_or_grant_amount=payload.amount,
        current_balance=payload.amount or 0.0,
        allowed_categories=payload.allowed_categories or None,
        disallowed_categories=payload.disallowed_categories or None,
        grantor=payload.grantor,
        start_date=payload.start_date,
        end_date=payload.end_date,
        approval_required=True,
        report_deadlines=[d.model_dump(mode="json") for d in payload.report_deadlines] or None,
    )
    db.add(pot)
    db.commit()
    db.refresh(pot)

    log_action(
        db, action="intake.grant_pot_created", workspace_id=workspace_id, user_id=current_user.id,
        details={"pot_id": pot.id, "name": pot.name, "amount": payload.amount},
    )
    return _to_out(pot, [])
