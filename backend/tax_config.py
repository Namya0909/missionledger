"""Every tax rate, dollar limit, and due date the Tax Prep Pack uses — one file so
there's exactly one place to check and update when a number changes. None of this
is tax advice; it's the organizing logic behind "Prepared to help you file" (see
TAX_DISCLAIMER). Every figure below is sourced from a specific IRS/state rule as of
when this was written — VERIFY each one on irs.gov or your state's site before
relying on it; thresholds, rates, and due dates change from year to year.
"""

# A handful of common state sales-tax rates, used both to size a new business's
# suggested "Sales Tax Savings" pot at setup time (ai/setup_agent.py) and to compute
# the Tax Prep Pack's sales-tax worksheet. Clearly an estimate, not advice — flagged
# as such (via rate_is_estimate / rate_is_estimate-equivalent) whenever a workspace's
# state isn't in this table or wasn't set at all. VERIFY on your state's revenue site.
STATE_SALES_TAX_RATES = {
    "CT": 0.0635, "NY": 0.04, "NJ": 0.06625, "MA": 0.0625, "CA": 0.0725,
    "TX": 0.0625, "FL": 0.06, "PA": 0.06, "IL": 0.0625, "WA": 0.065,
    "GA": 0.04, "OH": 0.0575, "NC": 0.0475, "MI": 0.06, "VA": 0.053,
}
DEFAULT_SALES_TAX_RATE = 0.06

# IRS Form 990 filing-requirement thresholds, based on gross receipts (and, for the
# 990-EZ, total assets) — current as of the 2024 filing cycle. VERIFY on
# irs.gov/charities-non-profits before relying on these; they're periodically updated.
FORM_990N_THRESHOLD = 50_000  # gross receipts <= this: can file the 990-N e-Postcard
FORM_990EZ_RECEIPTS_THRESHOLD = 200_000
FORM_990EZ_ASSETS_THRESHOLD = 500_000
IRS_990_INFO_URL = "https://www.irs.gov/charities-non-profits/exempt-organization-annual-filing-requirements-overview"

# A written donor acknowledgment is required for any single contribution of $250 or
# more (IRS Publication 1771). VERIFY this hasn't changed before relying on it.
DONOR_ACK_THRESHOLD = 250

# A business generally must issue Form 1099-NEC to a non-employee paid $600+ in a
# year for services. VERIFY on irs.gov/forms-pubs/about-form-1099-nec — this does not
# apply to payments for goods, or to most incorporated payees, which Python here has
# no way to know; the Tax Prep Pack surfaces candidates for a human to review, never
# a final determination.
CONTRACTOR_1099_THRESHOLD = 600

# Categories that are never a 1099-NEC candidate, excluded from the scan entirely
# (not just "flagged for review") — W-2 payroll is categorically ineligible (1099-NEC
# is only for non-employees), and a transfer between a business's own pots isn't a
# payment to an outside party at all.
CONTRACTOR_1099_EXCLUDED_CATEGORIES = {
    "payroll", "salaries", "reserve transfer", "tax reserve", "savings transfer", "processing fees",
}

# Standard quarterly estimated-tax due dates for a calendar-year filer, as (month, day)
# — the IRS shifts the exact date a few days some years for weekends/holidays. VERIFY
# the current year's exact date on irs.gov/payments/estimated-taxes before relying on
# it. The last entry rolls into the following calendar year (Jan 15).
ESTIMATED_TAX_QUARTER_DATES = [(4, 15), (6, 15), (9, 15), (1, 15)]

# Keyword match against a group transaction's Transaction.category (case-insensitive)
# for a year-end "possibly tax-relevant" summary — a plain keyword match, never a
# determination of actual deductibility (every item is labeled "possibly relevant,
# confirm with a tax professional" wherever it's shown).
GROUP_TAX_RELEVANT_CATEGORIES = {
    "charitable donation": "Charitable donations",
    "donation": "Charitable donations",
    "medical": "Medical expenses",
    "childcare": "Childcare",
    "daycare": "Childcare",
    "student loan": "Student loan interest",
    "home office": "Home office",
}

TAX_DISCLAIMER = "Prepared to help you file. Not tax advice. Please review with a CPA or tax professional."
