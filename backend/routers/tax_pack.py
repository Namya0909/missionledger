"""The Tax Prep Pack: organizes paperwork for tax time — never files, never advises.
Same access tier as Reports (any member can view/generate); gated additionally on
workspace.tax_pack_enabled, toggled from the Members tab (see PUT /tax-pack on
routers/workspaces.py). The JSON preview never calls the AI (instant, always
available); only the PDF adds AI-written explanatory prose, and does so with a
soft fallback (routers/attention.py's graceful-degrade pattern) — an AI outage or
exhausted budget still produces a usable PDF with plain default sentences instead
of failing the whole request, since the actual value here is the organized numbers.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

import models
import schemas
import tax_csv_builder
import tax_pdf_builder
import tax_prep
from ai.tax_pack import generate_business_tax_narrative, generate_group_tax_narrative, generate_nonprofit_tax_narrative
from auth import get_current_user, require_membership
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces/{workspace_id}/tax-pack", tags=["tax-pack"])


def _require_enabled(workspace: models.Workspace) -> None:
    if not workspace.tax_pack_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "The Tax Prep Pack isn't turned on for this workspace yet — ask someone who manages "
            "members to enable it from the Members tab.",
        )


def _load(workspace_id: int, db: Session) -> tuple[models.Workspace, list[models.Pot], list[models.Transaction], list[models.RecurringCharge]]:
    workspace = db.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
    transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
    recurring = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
    return workspace, pots, transactions, recurring


@router.get("")
def get_tax_pack_preview(
    workspace_id: int,
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    workspace, pots, transactions, _ = _load(workspace_id, db)
    _require_enabled(workspace)

    if workspace.type == models.WorkspaceType.group:
        data = tax_prep.group_tax_summary(transactions, year)
        return schemas.GroupTaxSummaryOut(
            year=year,
            buckets=[schemas.GroupTaxBucketOut(label=b.label, total=b.total, items=[schemas.TaxLineItemOut(**vars(i)) for i in b.items]) for b in data.buckets],
            grand_total=data.grand_total,
        )
    if workspace.type == models.WorkspaceType.nonprofit:
        data = tax_prep.nonprofit_tax_summary(pots, transactions, year)
        return schemas.NonprofitTaxSummaryOut(
            year=year,
            gross_receipts=data.gross_receipts,
            total_spending=data.total_spending,
            bucket_totals=data.bucket_totals,
            total_assets=data.total_assets,
            filing_recommendation=data.filing_recommendation,
            filing_reason=data.filing_reason,
            irs_990_info_url="https://www.irs.gov/charities-non-profits/exempt-organization-annual-filing-requirements-overview",
            donors=[schemas.DonorOut(donor_name=d.donor_name, amount=d.amount, date=d.date) for d in data.donors],
        )
    data = tax_prep.business_tax_summary(pots, transactions, year, workspace.state, date.today())
    return schemas.BusinessTaxSummaryOut(
        year=year,
        taxable_sales=data.taxable_sales,
        sales_tax_rate=data.sales_tax_rate,
        rate_is_estimate=data.rate_is_estimate,
        tax_owed=data.tax_owed,
        already_saved=data.already_saved,
        next_estimated_due_date=data.next_estimated_due_date,
        contractors=[schemas.ContractorOut(merchant=c.merchant, total_paid=c.total_paid) for c in data.contractors],
    )


@router.post("/pdf")
async def generate_tax_pack_pdf(
    workspace_id: int,
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    workspace, pots, transactions, _ = _load(workspace_id, db)
    _require_enabled(workspace)

    if workspace.type == models.WorkspaceType.group:
        data = tax_prep.group_tax_summary(transactions, year)
        try:
            narrative = (await generate_group_tax_narrative(db, workspace_id=workspace_id, user_id=current_user.id, data=data)).bucket_sentences
        except Exception:
            logger.exception("Tax Prep Pack narrative failed for workspace %s", workspace_id)
            narrative = [f"${b.total:,.2f} in {b.label.lower()} was logged this year — bring these to your tax preparer." for b in data.buckets]
        pdf_bytes = tax_pdf_builder.build_group_tax_pdf(workspace.name, data, narrative)
    elif workspace.type == models.WorkspaceType.nonprofit:
        data = tax_prep.nonprofit_tax_summary(pots, transactions, year)
        try:
            filing_summary, donor_letters = await generate_nonprofit_tax_narrative(
                db, workspace_id=workspace_id, user_id=current_user.id, org_name=workspace.name, data=data
            )
        except Exception:
            logger.exception("Tax Prep Pack narrative failed for workspace %s", workspace_id)
            filing_summary = data.filing_reason
            donor_letters = [
                f"Thank you for your generous gift of ${d.amount:,.2f} to {workspace.name}, received on "
                f"{d.date.strftime('%B %d, %Y')}. No goods or services were provided in exchange for this "
                "contribution, other than intangible religious benefits, if applicable."
                for d in data.donors
            ]
        pdf_bytes = tax_pdf_builder.build_nonprofit_tax_pdf(workspace.name, data, filing_summary, donor_letters)
    else:
        data = tax_prep.business_tax_summary(pots, transactions, year, workspace.state, date.today())
        try:
            narrative = await generate_business_tax_narrative(db, workspace_id=workspace_id, user_id=current_user.id, data=data)
        except Exception:
            logger.exception("Tax Prep Pack narrative failed for workspace %s", workspace_id)
            narrative = (
                f"${data.tax_owed:,.2f} in sales tax is owed on ${data.taxable_sales:,.2f} of taxable sales, "
                f"with ${data.already_saved:,.2f} already set aside. Next estimated-tax due date: "
                f"{data.next_estimated_due_date.strftime('%B %d, %Y')}."
            )
        pdf_bytes = tax_pdf_builder.build_business_tax_pdf(workspace.name, data, narrative)

    filename = f"{workspace.name.replace(' ', '_')}_tax_prep_pack_{year}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/csv")
def get_tax_pack_csv(
    workspace_id: int,
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_membership(workspace_id, current_user, db)
    workspace, pots, transactions, _ = _load(workspace_id, db)
    _require_enabled(workspace)

    if workspace.type == models.WorkspaceType.group:
        csv_text = tax_csv_builder.build_group_tax_csv(tax_prep.group_tax_summary(transactions, year))
    elif workspace.type == models.WorkspaceType.nonprofit:
        csv_text = tax_csv_builder.build_nonprofit_tax_csv(tax_prep.nonprofit_tax_summary(pots, transactions, year))
    else:
        csv_text = tax_csv_builder.build_business_tax_csv(tax_prep.business_tax_summary(pots, transactions, year, workspace.state, date.today()))

    filename = f"{workspace.name.replace(' ', '_')}_tax_prep_pack_{year}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
