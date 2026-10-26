"""tax_prep.py is pure Python (no AI, no DB query — just already-loaded lists of
ORM objects), so these build plain in-memory Transaction/Pot instances directly,
same spirit as test_savings_math.py testing compute_savings_analysis() in isolation.
"""

from datetime import date

import models
import tax_prep
from tax_config import CONTRACTOR_1099_THRESHOLD, FORM_990EZ_ASSETS_THRESHOLD, FORM_990N_THRESHOLD

THIS_YEAR = date.today().year


def _txn(pot_id=1, amount=100.0, category="Food", merchant="Vendor", day=1, status=models.TransactionStatus.approved, has_receipt=False):
    return models.Transaction(
        pot_id=pot_id,
        date=date(THIS_YEAR, 6, day),
        merchant=merchant,
        amount=amount,
        category=category,
        status=status,
        receipt_path="receipts/x.jpg" if has_receipt else None,
        created_by_user_id=1,
    )


def _pot(id=1, type_=models.PotType.free_use, name="General", current_balance=0.0):
    pot = models.Pot(workspace_id=1, name=name, type=type_)
    pot.id = id
    pot.current_balance = current_balance
    return pot


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------

def test_group_donation_and_medical_bucketed():
    txns = [
        _txn(amount=300.0, category="Donation", merchant="Jane Doe", day=1),
        _txn(amount=180.0, category="Medical", merchant="Clinic", day=2),
        _txn(amount=50.0, category="Groceries", merchant="Store", day=3),  # not tax-relevant, excluded
    ]
    data = tax_prep.group_tax_summary(txns, THIS_YEAR)
    labels = {b.label: b.total for b in data.buckets}
    assert labels["Charitable donations"] == 300.0
    assert labels["Medical expenses"] == 180.0
    assert "Groceries" not in labels
    assert data.grand_total == 480.0


def test_group_excludes_other_years_and_negative_amounts():
    txns = [
        _txn(amount=300.0, category="Donation", merchant="Jane Doe", day=1),
        models.Transaction(
            pot_id=1, date=date(THIS_YEAR - 1, 6, 1), merchant="Old Donor", amount=200.0,
            category="Donation", status=models.TransactionStatus.approved, created_by_user_id=1,
        ),
        _txn(amount=-50.0, category="Donation", merchant="Refund", day=2),  # negative = not an expense
    ]
    data = tax_prep.group_tax_summary(txns, THIS_YEAR)
    assert data.grand_total == 300.0


# ---------------------------------------------------------------------------
# Nonprofit
# ---------------------------------------------------------------------------

def test_nonprofit_990n_for_small_org():
    pots = [_pot(current_balance=10_000)]
    txns = [_txn(amount=-(FORM_990N_THRESHOLD - 1), category="Donation", merchant="Donor A", day=1)]
    data = tax_prep.nonprofit_tax_summary(pots, txns, THIS_YEAR)
    assert data.gross_receipts == FORM_990N_THRESHOLD - 1
    assert data.filing_recommendation == "990-N"


def test_nonprofit_990ez_over_990n_threshold_small_assets():
    pots = [_pot(current_balance=10_000)]
    txns = [_txn(amount=-(FORM_990N_THRESHOLD + 1), category="Donation", merchant="Donor A", day=1)]
    data = tax_prep.nonprofit_tax_summary(pots, txns, THIS_YEAR)
    assert data.filing_recommendation == "990-EZ"


def test_nonprofit_full_990_over_asset_threshold():
    pots = [_pot(current_balance=FORM_990EZ_ASSETS_THRESHOLD + 1)]
    txns = [_txn(amount=-(FORM_990N_THRESHOLD + 1), category="Donation", merchant="Donor A", day=1)]
    data = tax_prep.nonprofit_tax_summary(pots, txns, THIS_YEAR)
    assert data.filing_recommendation == "990"


def test_nonprofit_donor_list_only_captures_donations_over_threshold():
    pots = [_pot()]
    txns = [
        _txn(amount=-300.0, category="Donation", merchant="Big Donor", day=1),
        _txn(amount=-100.0, category="Donation", merchant="Small Donor", day=2),  # under $250, excluded
        _txn(amount=-500.0, category="Grant Income", merchant="Grantor", day=3),  # not a "Donation", excluded
    ]
    data = tax_prep.nonprofit_tax_summary(pots, txns, THIS_YEAR)
    names = {d.donor_name for d in data.donors}
    assert names == {"Big Donor"}


def test_nonprofit_spending_buckets_reuse_reports_logic():
    pots = [_pot()]
    txns = [_txn(amount=500.0, category="Rent", day=1), _txn(amount=300.0, category="Youth Meals", day=2)]
    data = tax_prep.nonprofit_tax_summary(pots, txns, THIS_YEAR)
    assert data.bucket_totals["Management & General"] == 500.0
    assert data.bucket_totals["Program Services"] == 300.0


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------

def test_business_sales_tax_known_state_rate():
    pots = [_pot(id=1, type_=models.PotType.free_use)]
    txns = [_txn(pot_id=1, amount=-1000.0, category="Sales", day=1)]
    data = tax_prep.business_tax_summary(pots, txns, THIS_YEAR, "CT", date(THIS_YEAR, 7, 1))
    assert data.taxable_sales == 1000.0
    assert data.rate_is_estimate is False
    assert data.tax_owed == round(1000.0 * 0.0635, 2)


def test_business_sales_tax_unknown_state_flagged_as_estimate():
    pots = [_pot(id=1, type_=models.PotType.free_use)]
    txns = [_txn(pot_id=1, amount=-1000.0, category="Sales", day=1)]
    data = tax_prep.business_tax_summary(pots, txns, THIS_YEAR, None, date(THIS_YEAR, 7, 1))
    assert data.rate_is_estimate is True


def test_business_already_saved_from_tax_reserve_pot():
    pots = [_pot(id=1, type_=models.PotType.free_use), _pot(id=2, type_=models.PotType.reserve, name="Sales Tax Savings", current_balance=250.0)]
    data = tax_prep.business_tax_summary(pots, [], THIS_YEAR, "CT", date(THIS_YEAR, 7, 1))
    assert data.already_saved == 250.0


def test_business_contractor_threshold_excludes_under_600():
    pots = [_pot(id=1, type_=models.PotType.free_use)]
    txns = [
        _txn(pot_id=1, amount=CONTRACTOR_1099_THRESHOLD, category="Repairs", merchant="Handy Co", day=1),
        _txn(pot_id=1, amount=CONTRACTOR_1099_THRESHOLD - 1, category="Supplies", merchant="Under Co", day=2),
    ]
    data = tax_prep.business_tax_summary(pots, txns, THIS_YEAR, "CT", date(THIS_YEAR, 7, 1))
    merchants = {c.merchant for c in data.contractors}
    assert merchants == {"Handy Co"}


def test_business_contractor_list_excludes_payroll_and_internal_transfers():
    pots = [_pot(id=1, type_=models.PotType.free_use)]
    txns = [
        _txn(pot_id=1, amount=5000.0, category="Payroll", merchant="Payroll - Staff", day=1),
        _txn(pot_id=1, amount=1000.0, category="Reserve Transfer", merchant="Transfer to reserve", day=2),
        _txn(pot_id=1, amount=900.0, category="Repairs", merchant="Fix-It Co", day=3),
    ]
    data = tax_prep.business_tax_summary(pots, txns, THIS_YEAR, "CT", date(THIS_YEAR, 7, 1))
    merchants = {c.merchant for c in data.contractors}
    assert merchants == {"Fix-It Co"}


def test_business_next_due_date_is_in_the_future():
    pots = [_pot(id=1, type_=models.PotType.free_use)]
    today = date(THIS_YEAR, 7, 1)
    data = tax_prep.business_tax_summary(pots, [], THIS_YEAR, "CT", today)
    assert data.next_estimated_due_date >= today
