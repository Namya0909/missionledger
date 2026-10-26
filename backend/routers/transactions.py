import logging
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

import models
import schemas
from ai.agent import TransactionReview, review_transaction
from ai.rules_checker import check_new_transaction
from audit import log_action
from auth import get_current_user, require_membership
from config import UPLOADS_DIR, MissingAIKeyError
from database import get_db
from file_encryption import decrypt_bytes, encrypt_bytes
from file_validation import sniff_matches_declared_type
from models import DEPOSIT_POT_TYPES, TransactionStatus
from permissions import (
    can_create_transaction,
    can_decide,
    can_edit_or_delete_transaction,
    can_manage_pots,
    needs_approval,
    waiting_reason,
)
from security_log import log_security_event

# App-wide upload policy: CSV, PNG, JPG, or PDF only, 5 MB max (see also routers/intake.py).
ALLOWED_RECEIPT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
MAX_RECEIPT_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/workspaces/{workspace_id}/transactions", tags=["transactions"])
logger = logging.getLogger(__name__)


def get_pot_or_404(workspace_id: int, pot_id: int, db: Session) -> models.Pot:
    pot = db.query(models.Pot).filter_by(id=pot_id, workspace_id=workspace_id).first()
    if pot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pot not found")
    return pot


def get_workspace_or_404(workspace_id: int, db: Session) -> models.Workspace:
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace


def _apply_balance_change(pot: models.Pot, transaction: models.Transaction, approve: bool) -> None:
    if not approve:
        return
    if pot.type in DEPOSIT_POT_TYPES:
        pot.current_balance += transaction.amount
    else:
        pot.current_balance -= transaction.amount


def _reverse_balance_change(pot: models.Pot, transaction: models.Transaction) -> None:
    """Undoes exactly what _apply_balance_change(pot, transaction, approve=True) did —
    used when editing or deleting a transaction that was already approved, since its
    amount already moved pot.current_balance once and that has to be undone before
    the new amount (or nothing, on delete) takes its place."""
    if pot.type in DEPOSIT_POT_TYPES:
        pot.current_balance -= transaction.amount
    else:
        pot.current_balance += transaction.amount


def to_out(
    transaction: models.Transaction,
    pot: models.Pot,
    current_user_id: int | None = None,
    can_manage_pots_here: bool = False,
) -> schemas.TransactionOut:
    can_i_decide = False
    decide_blocked_reason = None
    if current_user_id is not None and transaction.status == TransactionStatus.pending:
        can_i_decide, decide_blocked_reason = can_decide(pot, transaction, current_user_id)
        if can_i_decide:
            decide_blocked_reason = None
    can_i_edit = current_user_id is not None and (
        transaction.created_by_user_id == current_user_id or can_manage_pots_here
    )
    return schemas.TransactionOut(
        id=transaction.id,
        workspace_id=transaction.workspace_id,
        pot_id=transaction.pot_id,
        pot_name=pot.name,
        date=transaction.date,
        merchant=transaction.merchant,
        description=transaction.description,
        amount=transaction.amount,
        category=transaction.category,
        status=transaction.status,
        source=transaction.source,
        warnings=transaction.warnings,
        rejection_reason=transaction.rejection_reason,
        waiting_reason=waiting_reason(pot, transaction),
        can_i_decide=can_i_decide,
        decide_blocked_reason=decide_blocked_reason,
        can_i_edit=can_i_edit,
        has_receipt=bool(transaction.receipt_path),
        created_by_user_id=transaction.created_by_user_id,
        created_by_name=transaction.created_by.name,
        approved_by_user_id=transaction.approved_by_user_id,
        created_at=transaction.created_at,
    )


def decide(
    db: Session,
    *,
    workspace_id: int,
    transaction: models.Transaction,
    pot: models.Pot,
    current_user: models.User,
    approve: bool,
    reason: str | None,
) -> models.Transaction:
    """Shared by the single-decision endpoint below and the bulk approvals endpoint."""
    allowed, deny_reason = can_decide(pot, transaction, current_user.id)
    if not allowed:
        # A blocked attempt is itself worth a history-log entry (e.g. catching someone
        # repeatedly trying to approve their own expense) — not just completed decisions.
        log_action(
            db,
            action="transaction.decision_blocked",
            workspace_id=workspace_id,
            user_id=current_user.id,
            details={"transaction_id": transaction.id, "attempted_approve": approve, "reason": deny_reason},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, deny_reason)
    if transaction.status != TransactionStatus.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This transaction was already decided")
    if not approve and not reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A reason is required to reject an expense")

    transaction.status = TransactionStatus.approved if approve else TransactionStatus.rejected
    transaction.rejection_reason = None if approve else reason
    _apply_balance_change(pot, transaction, approve=approve)
    transaction.approved_by_user_id = current_user.id
    db.commit()
    db.refresh(transaction)

    log_action(
        db,
        action="transaction.decided",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"transaction_id": transaction.id, "approved": approve, "reason": reason},
    )
    return transaction


@router.post("", response_model=schemas.TransactionOut)
async def create_transaction(
    workspace_id: int,
    payload: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    workspace = get_workspace_or_404(workspace_id, db)
    if not can_create_transaction(membership, workspace.type):
        log_security_event(
            db, defense="Access Control", action="blocked",
            detail="Role lacks permission to add expenses.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot add expenses")

    pot = get_pot_or_404(workspace_id, payload.pot_id, db)

    # A flaky or filtered AI call (rate limit, provider content filter, etc.) should
    # never block recording a real expense — fall back to no AI review rather than
    # failing the whole request. MissingAIKeyError (no key configured at all) is a
    # setup problem the user should actually see, so it still propagates to the 503
    # handler in main.py. Note: pydantic_ai's own provider-error classes (timeouts,
    # auth failures, rate limits) all subclass RuntimeError too, so catching plain
    # RuntimeError here would wrongly treat every one of them as "no key configured."
    try:
        review = await review_transaction(
            db,
            pot=pot,
            date=payload.date,
            merchant=payload.merchant,
            description=payload.description,
            amount=payload.amount,
            workspace_id=workspace_id,
            user_id=current_user.id,
        )
    except MissingAIKeyError:
        raise
    except Exception:
        logger.exception("Transaction review failed for workspace %s", workspace_id)
        review = TransactionReview(category=payload.category or "Uncategorized", warnings=[], reasoning="AI review unavailable.")

    requires_approval = needs_approval(pot, payload.amount)

    transaction = models.Transaction(
        workspace_id=workspace_id,
        pot_id=pot.id,
        date=payload.date,
        merchant=payload.merchant,
        description=payload.description,
        amount=payload.amount,
        category=payload.category or review.category,
        source=payload.source,
        warnings=review.warnings,
        status=TransactionStatus.pending if requires_approval else TransactionStatus.approved,
        created_by_user_id=current_user.id,
    )
    if not requires_approval:
        _apply_balance_change(pot, transaction, approve=True)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # The Rules Checker runs after the transaction has an id (so category/grant/
    # over-budget checks can reference it specifically) but still before the user
    # ever sees it — the same "never block on an AI hiccup" rule as the review above.
    rules_warnings = await check_new_transaction(
        db, transaction=transaction, pot=pot, workspace_id=workspace_id, user_id=current_user.id
    )
    if rules_warnings:
        transaction.warnings = [*(transaction.warnings or []), *rules_warnings]
        db.commit()
        db.refresh(transaction)

    log_action(
        db,
        action="transaction.created",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={
            "transaction_id": transaction.id,
            "amount": payload.amount,
            "warnings": transaction.warnings,
            "required_approval": requires_approval,
        },
    )
    return to_out(transaction, pot, current_user.id, can_manage_pots(membership, workspace.type))


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    workspace_id: int,
    pot_id: int | None = None,
    status_filter: TransactionStatus | None = None,
    created_by_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    query = db.query(models.Transaction).filter_by(workspace_id=workspace_id)
    if pot_id is not None:
        query = query.filter_by(pot_id=pot_id)
    if status_filter is not None:
        query = query.filter_by(status=status_filter)
    if created_by_user_id is not None:
        query = query.filter_by(created_by_user_id=created_by_user_id)
    transactions = query.order_by(models.Transaction.date.desc()).all()

    pots_by_id = {p.id: p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}
    can_manage_pots_here = can_manage_pots(membership, membership.workspace.type)
    return [to_out(t, pots_by_id[t.pot_id], current_user.id, can_manage_pots_here) for t in transactions]


@router.post("/{transaction_id}/decision", response_model=schemas.TransactionOut)
def decide_transaction(
    workspace_id: int,
    transaction_id: int,
    payload: schemas.TransactionDecision,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    transaction = (
        db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
    )
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    pot = get_pot_or_404(workspace_id, transaction.pot_id, db)

    transaction = decide(
        db,
        workspace_id=workspace_id,
        transaction=transaction,
        pot=pot,
        current_user=current_user,
        approve=payload.approve,
        reason=payload.reason,
    )
    return to_out(transaction, pot, current_user.id, can_manage_pots(membership, membership.workspace.type))


@router.put("/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    workspace_id: int,
    transaction_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    transaction = db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    workspace_type = membership.workspace.type
    if not can_edit_or_delete_transaction(transaction, membership, workspace_type, current_user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only edit your own expenses, or any expense if you manage pots"
        )

    old_pot = get_pot_or_404(workspace_id, transaction.pot_id, db)
    new_pot = get_pot_or_404(workspace_id, payload.pot_id, db)
    old_values = {"pot_name": old_pot.name, "amount": transaction.amount, "merchant": transaction.merchant}

    # The transaction's amount/pot may already have moved pot.current_balance once
    # (if it's approved) — reverse that old effect before applying the new one, same
    # math _apply_balance_change used going the other way. Pending/rejected ones
    # never touched a balance, so there's nothing to reverse or reapply for those.
    if transaction.status == TransactionStatus.approved:
        _reverse_balance_change(old_pot, transaction)

    transaction.pot_id = payload.pot_id
    transaction.date = payload.date
    transaction.merchant = payload.merchant
    transaction.description = payload.description
    transaction.amount = payload.amount
    transaction.category = payload.category

    if transaction.status == TransactionStatus.approved:
        _apply_balance_change(new_pot, transaction, approve=True)

    db.commit()
    db.refresh(transaction)

    log_action(
        db,
        action="transaction.updated",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={
            "transaction_id": transaction.id,
            "old": old_values,
            "new": {"pot_name": new_pot.name, "amount": transaction.amount, "merchant": transaction.merchant},
        },
    )
    return to_out(transaction, new_pot, current_user.id, can_manage_pots(membership, workspace_type))


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    workspace_id: int,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    membership = require_membership(workspace_id, current_user, db)
    transaction = db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    if not can_edit_or_delete_transaction(transaction, membership, membership.workspace.type, current_user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only delete your own expenses, or any expense if you manage pots"
        )

    pot = get_pot_or_404(workspace_id, transaction.pot_id, db)
    if transaction.status == TransactionStatus.approved:
        _reverse_balance_change(pot, transaction)

    if transaction.receipt_path:
        (UPLOADS_DIR / transaction.receipt_path).unlink(missing_ok=True)

    details = {"transaction_id": transaction.id, "amount": transaction.amount, "merchant": transaction.merchant, "pot_name": pot.name}
    db.delete(transaction)
    db.commit()

    log_action(db, action="transaction.deleted", workspace_id=workspace_id, user_id=current_user.id, details=details)


@router.post("/{transaction_id}/receipt", response_model=schemas.TransactionOut)
async def upload_receipt(
    workspace_id: int,
    transaction_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Any member can attach a receipt photo/PDF to a transaction they can see —
    it's just supporting evidence, not a money-moving action."""
    require_membership(workspace_id, current_user, db)
    transaction = db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    pot = get_pot_or_404(workspace_id, transaction.pot_id, db)

    extension = ALLOWED_RECEIPT_TYPES.get(file.content_type)
    if extension is None:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: content type '{file.content_type}' is not PNG, JPG, or PDF.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Receipts must be a PNG, JPG, or PDF")

    contents = await file.read()
    if len(contents) > MAX_RECEIPT_BYTES:
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: {len(contents)} bytes exceeds the 5 MB limit.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Receipt file is too large (max 5 MB)")
    if not sniff_matches_declared_type(contents, file.content_type):
        log_security_event(
            db, defense="Upload Validation", action="rejected",
            detail=f"Receipt upload rejected: file content doesn't match its claimed type '{file.content_type}'.",
            workspace_id=workspace_id, user_id=current_user.id,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This file doesn't look like a real PNG, JPG, or PDF")

    workspace_dir = UPLOADS_DIR / str(workspace_id)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    # Random filename (not the transaction id) — the id is guessable, so naming
    # the file after it would let someone enumerate receipt URLs even though the
    # GET endpoint itself is membership-gated; this is defense in depth. Encrypted
    # at rest (see file_encryption.py) — protects a receipt's contents from anyone
    # with raw disk/backup access but not the app's own auth.
    dest = workspace_dir / f"{secrets.token_urlsafe(16)}{extension}"
    dest.write_bytes(encrypt_bytes(contents))

    transaction.receipt_path = str(dest.relative_to(UPLOADS_DIR))
    transaction.source = models.TransactionSource.receipt_photo
    db.commit()
    db.refresh(transaction)

    log_action(
        db,
        action="transaction.receipt_uploaded",
        workspace_id=workspace_id,
        user_id=current_user.id,
        details={"transaction_id": transaction.id},
    )
    return to_out(transaction, pot, current_user.id)


@router.get("/{transaction_id}/receipt")
def get_receipt(
    workspace_id: int,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    transaction = db.query(models.Transaction).filter_by(id=transaction_id, workspace_id=workspace_id).first()
    if transaction is None or not transaction.receipt_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No receipt on this transaction")

    path = UPLOADS_DIR / transaction.receipt_path
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receipt file is missing")

    try:
        decrypted = decrypt_bytes(path.read_bytes())
    except ValueError:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Receipt file could not be read")

    extension = path.suffix
    media_type = next((ct for ct, ext in ALLOWED_RECEIPT_TYPES.items() if ext == extension), "application/octet-stream")
    return Response(content=decrypted, media_type=media_type)
