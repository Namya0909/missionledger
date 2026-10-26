"""Pure Python report math — every number in the Reporter's PDF comes from here,
never from the AI. ai/reporter.py only writes the narrative sentences around
numbers this module already computed, same pattern as every other helper.
"""

from dataclasses import dataclass, field
from datetime import date

import models
from rules import find_issues, pot_usage
from settleup import compute_settle_up

# A small, visible, inspectable rule rather than an AI guess — categories not
# listed here default to "Program Services," since most nonprofit spending is
# direct program delivery (grant-funded purchases, service categories).
CATEGORY_TO_990_BUCKET = {
    "rent": "Management & General",
    "utilities": "Management & General",
    "phone": "Management & General",
    "office supplies": "Management & General",
    "insurance": "Management & General",
    "admin": "Management & General",
}


def _bucket_for_category(category: str | None) -> str:
    key = (category or "").strip().lower()
    if "fundrais" in key:
        return "Fundraising"
    return CATEGORY_TO_990_BUCKET.get(key, "Program Services")


@dataclass
class GrantReportData:
    pot_name: str
    grantor: str | None
    budget: float
    spent: float
    remaining: float
    pct_used: float
    end_date: date | None
    report_deadlines: list[dict]


@dataclass
class NonprofitReportData:
    grants: list[GrantReportData] = field(default_factory=list)
    bucket_totals: dict[str, float] = field(default_factory=dict)  # 990 buckets
    total_spent: float = 0.0


@dataclass
class GroupReportData:
    wins: list[str] = field(default_factory=list)
    overspending: list[str] = field(default_factory=list)
    goal_progress: list[dict] = field(default_factory=list)
    balances: list[dict] = field(default_factory=list)
    transfers: list[dict] = field(default_factory=list)


@dataclass
class BusinessReportData:
    sales: float = 0.0
    costs: float = 0.0
    net: float = 0.0
    reserve_status: list[dict] = field(default_factory=list)
    payroll_status: dict | None = None
    runway_months: float | None = None
    action_candidates: list[str] = field(default_factory=list)


def pending_approvals(pots: list[models.Pot], transactions: list[models.Transaction]) -> list[dict]:
    pots_by_id = {p.id: p for p in pots}
    pending = [t for t in transactions if t.status == models.TransactionStatus.pending]
    return [
        {
            "pot_name": pots_by_id[t.pot_id].name if t.pot_id in pots_by_id else "?",
            "merchant": t.merchant,
            "amount": t.amount,
            "date": t.date.isoformat(),
        }
        for t in pending
    ]


def nonprofit_report(pots: list[models.Pot], transactions: list[models.Transaction], today: date) -> NonprofitReportData:
    data = NonprofitReportData()
    bucket_totals: dict[str, float] = {"Program Services": 0.0, "Management & General": 0.0, "Fundraising": 0.0}

    for pot in pots:
        if pot.type == models.PotType.restricted_grant:
            spent = (pot.budget_or_grant_amount or 0.0) - pot.current_balance
            budget = pot.budget_or_grant_amount or 0.0
            data.grants.append(
                GrantReportData(
                    pot_name=pot.name,
                    grantor=pot.grantor,
                    budget=budget,
                    spent=round(spent, 2),
                    remaining=round(pot.current_balance, 2),
                    pct_used=round(spent / budget * 100, 1) if budget else 0.0,
                    end_date=pot.end_date,
                    report_deadlines=pot.report_deadlines or [],
                )
            )
        approved = [t for t in transactions if t.pot_id == pot.id and t.status == models.TransactionStatus.approved and t.amount > 0]
        for t in approved:
            bucket_totals[_bucket_for_category(t.category)] += t.amount

    data.bucket_totals = {k: round(v, 2) for k, v in bucket_totals.items()}
    data.total_spent = round(sum(bucket_totals.values()), 2)
    return data


def group_report(pots: list[models.Pot], transactions: list[models.Transaction], member_user_ids: list[int], incomes: dict[int, float], names: dict[int, str], today: date) -> GroupReportData:
    data = GroupReportData()
    year, month = today.year, today.month

    for pot in pots:
        if pot.type == models.PotType.savings_goal:
            month_deposits = sum(
                t.amount for t in transactions
                if t.pot_id == pot.id and t.status == models.TransactionStatus.approved
                and t.date.year == year and t.date.month == month
            )
            if month_deposits > 0:
                data.wins.append(f"'{pot.name}' grew by ${month_deposits:,.2f} this month.")
            if pot.target_amount:
                data.goal_progress.append(
                    {"pot_name": pot.name, "current": round(pot.current_balance, 2), "target": pot.target_amount, "pct": round(pot.current_balance / pot.target_amount * 100, 1)}
                )
        else:
            usage = pot_usage(pot, transactions, today)
            if usage.status == "over":
                data.overspending.append(f"'{pot.name}' is over budget this month: ${usage.used:,.2f} of ${usage.limit:,.2f}.")

    settle_up = compute_settle_up(pots, transactions, member_user_ids, incomes)
    data.balances = [{"name": names.get(uid, "?"), "amount": round(amt, 2)} for uid, amt in settle_up.balances.items()]
    data.transfers = [
        {"from": names.get(t["from_user_id"], "?"), "to": names.get(t["to_user_id"], "?"), "amount": round(t["amount"], 2)}
        for t in settle_up.transfers
    ]
    return data


def business_report(pots: list[models.Pot], transactions: list[models.Transaction], recurring_charges: list[models.RecurringCharge], today: date) -> BusinessReportData:
    from rules import payroll_coverage

    data = BusinessReportData()
    year, month = today.year, today.month

    # Sales/costs for the last calendar month, in the Operating-style (free_use)
    # pot(s) — sales are recorded as negative amounts (money coming in), per the
    # app's convention for income landing in a non-deposit pot.
    operating_pots = [p for p in pots if p.type == models.PotType.free_use]
    operating_pot_ids = {p.id for p in operating_pots}
    last_month_txns = [
        t for t in transactions
        if t.pot_id in operating_pot_ids and t.status == models.TransactionStatus.approved
        and t.date.year == year and t.date.month == month
    ]
    data.sales = round(-sum(t.amount for t in last_month_txns if t.amount < 0), 2)
    data.costs = round(sum(t.amount for t in last_month_txns if t.amount > 0), 2)
    data.net = round(data.sales - data.costs, 2)

    for pot in pots:
        if pot.type == models.PotType.reserve:
            usage = pot_usage(pot, transactions, today)
            data.reserve_status.append(
                {"pot_name": pot.name, "current": round(pot.current_balance, 2), "target": usage.limit, "pct": round(usage.pct, 1) if usage.pct is not None else None}
            )

    payroll_pots = [p for p in pots if "payroll" in p.name.lower()]
    if payroll_pots:
        data.payroll_status = payroll_coverage(payroll_pots[0], transactions, recurring_charges, today)

    gross_expenses_3mo = sum(
        t.amount for t in transactions
        if t.pot_id in operating_pot_ids and t.status == models.TransactionStatus.approved
        and t.amount > 0 and (today - t.date).days <= 90
    )
    avg_monthly_expenses = gross_expenses_3mo / 3
    total_operating_balance = sum(p.current_balance for p in operating_pots)
    data.runway_months = round(total_operating_balance / avg_monthly_expenses, 1) if avg_monthly_expenses > 0 else None

    issues = find_issues(pots, transactions, today, recurring_charges)
    severity = {"payroll_not_covered": 3, "reserve_shortfall": 2, "over_budget": 2, "report_deadline_approaching": 2}
    ranked = sorted(issues, key=lambda i: severity.get(i.kind, 1), reverse=True)
    data.action_candidates = [i.detail for i in ranked]
    return data
