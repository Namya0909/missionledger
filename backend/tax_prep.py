"""Pure Python Tax Prep Pack math — every number here comes from Transaction/Pot
data already in the database, never from the AI. ai/tax_pack.py only writes the
explanatory prose and donor-letter text around numbers this module already computed,
same pattern as reports.py/ai/reporter.py. This organizes paperwork for tax time; it
never files a return, calculates a final liability, or gives tax advice — see
tax_config.TAX_DISCLAIMER, shown on every page this data ends up on.
"""

from dataclasses import dataclass, field
from datetime import date

import models
from reports import _bucket_for_category
from tax_config import (
    CONTRACTOR_1099_EXCLUDED_CATEGORIES,
    CONTRACTOR_1099_THRESHOLD,
    DEFAULT_SALES_TAX_RATE,
    DONOR_ACK_THRESHOLD,
    ESTIMATED_TAX_QUARTER_DATES,
    FORM_990EZ_ASSETS_THRESHOLD,
    FORM_990EZ_RECEIPTS_THRESHOLD,
    FORM_990N_THRESHOLD,
    GROUP_TAX_RELEVANT_CATEGORIES,
    IRS_990_INFO_URL,
    STATE_SALES_TAX_RATES,
)


@dataclass
class TaxLineItem:
    date: date
    merchant: str
    amount: float
    has_receipt: bool = False


@dataclass
class GroupTaxBucket:
    label: str
    total: float = 0.0
    items: list[TaxLineItem] = field(default_factory=list)


@dataclass
class GroupTaxData:
    year: int
    buckets: list[GroupTaxBucket] = field(default_factory=list)
    grand_total: float = 0.0


@dataclass
class Donor:
    donor_name: str
    amount: float
    date: date


@dataclass
class NonprofitTaxData:
    year: int
    gross_receipts: float = 0.0
    total_spending: float = 0.0
    bucket_totals: dict[str, float] = field(default_factory=dict)
    total_assets: float = 0.0
    filing_recommendation: str = "990-N"
    filing_reason: str = ""
    donors: list[Donor] = field(default_factory=list)


@dataclass
class Contractor:
    merchant: str
    total_paid: float


@dataclass
class BusinessTaxData:
    year: int
    taxable_sales: float = 0.0
    sales_tax_rate: float = DEFAULT_SALES_TAX_RATE
    rate_is_estimate: bool = True
    tax_owed: float = 0.0
    already_saved: float = 0.0
    next_estimated_due_date: date = field(default_factory=date.today)
    contractors: list[Contractor] = field(default_factory=list)


def _in_year(t: models.Transaction, year: int) -> bool:
    return t.date.year == year and t.status == models.TransactionStatus.approved


def group_tax_summary(transactions: list[models.Transaction], year: int) -> GroupTaxData:
    data = GroupTaxData(year=year)
    buckets_by_label: dict[str, GroupTaxBucket] = {}

    for t in transactions:
        if not _in_year(t, year) or t.amount <= 0:
            continue
        key = (t.category or "").strip().lower()
        label = GROUP_TAX_RELEVANT_CATEGORIES.get(key)
        if label is None:
            continue
        bucket = buckets_by_label.setdefault(label, GroupTaxBucket(label=label))
        bucket.items.append(TaxLineItem(date=t.date, merchant=t.merchant, amount=t.amount, has_receipt=bool(t.receipt_path)))
        bucket.total = round(bucket.total + t.amount, 2)

    data.buckets = sorted(buckets_by_label.values(), key=lambda b: b.label)
    data.grand_total = round(sum(b.total for b in data.buckets), 2)
    return data


def nonprofit_tax_summary(pots: list[models.Pot], transactions: list[models.Transaction], year: int) -> NonprofitTaxData:
    data = NonprofitTaxData(year=year)
    bucket_totals: dict[str, float] = {"Program Services": 0.0, "Management & General": 0.0, "Fundraising": 0.0}

    for t in transactions:
        if not _in_year(t, year):
            continue
        if t.amount < 0:
            data.gross_receipts += -t.amount
        else:
            data.total_spending += t.amount
            bucket_totals[_bucket_for_category(t.category)] += t.amount
        if "donation" in (t.category or "").lower() and -t.amount >= DONOR_ACK_THRESHOLD:
            data.donors.append(Donor(donor_name=t.merchant, amount=-t.amount, date=t.date))

    data.gross_receipts = round(data.gross_receipts, 2)
    data.total_spending = round(data.total_spending, 2)
    data.bucket_totals = {k: round(v, 2) for k, v in bucket_totals.items()}
    data.total_assets = round(sum(p.current_balance for p in pots), 2)
    data.donors.sort(key=lambda d: d.date)

    if data.gross_receipts <= FORM_990N_THRESHOLD:
        data.filing_recommendation = "990-N"
        data.filing_reason = (
            f"Gross receipts (${data.gross_receipts:,.2f}) are at or under the "
            f"${FORM_990N_THRESHOLD:,.0f} threshold for the 990-N e-Postcard."
        )
    elif data.gross_receipts < FORM_990EZ_RECEIPTS_THRESHOLD and data.total_assets < FORM_990EZ_ASSETS_THRESHOLD:
        data.filing_recommendation = "990-EZ"
        data.filing_reason = (
            f"Gross receipts (${data.gross_receipts:,.2f}) are under ${FORM_990EZ_RECEIPTS_THRESHOLD:,.0f} "
            f"and total assets (${data.total_assets:,.2f}) are under ${FORM_990EZ_ASSETS_THRESHOLD:,.0f}, "
            "so the shorter 990-EZ likely applies."
        )
    else:
        data.filing_recommendation = "990"
        data.filing_reason = (
            f"Gross receipts (${data.gross_receipts:,.2f}) or total assets (${data.total_assets:,.2f}) "
            "are over the 990-EZ thresholds, so the full Form 990 likely applies."
        )
    data.filing_reason += f" Confirm on {IRS_990_INFO_URL}."
    return data


def business_tax_summary(
    pots: list[models.Pot],
    transactions: list[models.Transaction],
    year: int,
    state: str | None,
    today: date,
) -> BusinessTaxData:
    data = BusinessTaxData(year=year)
    state_code = (state or "").upper()
    data.sales_tax_rate = STATE_SALES_TAX_RATES.get(state_code, DEFAULT_SALES_TAX_RATE)
    data.rate_is_estimate = state_code not in STATE_SALES_TAX_RATES

    operating_pot_ids = {p.id for p in pots if p.type == models.PotType.free_use}
    data.taxable_sales = round(
        -sum(t.amount for t in transactions if t.pot_id in operating_pot_ids and _in_year(t, year) and t.amount < 0), 2
    )
    data.tax_owed = round(data.taxable_sales * data.sales_tax_rate, 2)

    tax_reserve_pots = [p for p in pots if p.type == models.PotType.reserve and "tax" in p.name.lower()]
    data.already_saved = round(sum(p.current_balance for p in tax_reserve_pots), 2)

    # Build real due dates for a window spanning last year through next year — the
    # 4th quarter date (Jan 15) belongs to the year AFTER the 4/15-6/15-9/15 trio it
    # follows — then pick the first one on or after today.
    candidates = []
    for tax_year in (today.year - 1, today.year, today.year + 1):
        q1, q2, q3, q4 = ESTIMATED_TAX_QUARTER_DATES
        candidates += [date(tax_year, *q1), date(tax_year, *q2), date(tax_year, *q3), date(tax_year + 1, *q4)]
    data.next_estimated_due_date = min(c for c in candidates if c >= today)

    totals_by_merchant: dict[str, float] = {}
    for t in transactions:
        if not _in_year(t, year) or t.amount <= 0:
            continue
        if (t.category or "").strip().lower() in CONTRACTOR_1099_EXCLUDED_CATEGORIES:
            continue
        totals_by_merchant[t.merchant] = totals_by_merchant.get(t.merchant, 0.0) + t.amount
    data.contractors = sorted(
        (Contractor(merchant=m, total_paid=round(total, 2)) for m, total in totals_by_merchant.items() if total >= CONTRACTOR_1099_THRESHOLD),
        key=lambda c: -c.total_paid,
    )
    return data
