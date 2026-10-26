"""Pure, deterministic rule-checking — Python finds the problems and does every
calculation; the AI layer (ai/attention.py) only explains what Python already found.
No LLM call in this file ever decides a number.
"""

from dataclasses import dataclass
from datetime import date

import models

OVER_BUDGET_THRESHOLD = 1.0
WARNING_BUDGET_THRESHOLD = 0.8
GOAL_BEHIND_PACE_MARGIN = 0.15  # 15 percentage points behind the pace needed to hit the deadline


@dataclass
class PotUsage:
    pot_id: int
    pot_name: str
    period: str  # "this month" | "lifetime" | "goal"
    used: float
    limit: float | None
    pct: float | None  # 0..100+, None if there's no limit/target to compare against
    status: str  # "ok" | "warning" | "over"


@dataclass
class Issue:
    pot_id: int
    pot_name: str
    # "over_budget" | "disallowed_category" | "outside_grant_window" | "goal_behind_pace"
    # | "reserve_shortfall" | "payroll_not_covered" | "report_deadline_approaching"
    kind: str
    detail: str
    transaction_id: int | None = None


REPORT_DEADLINE_WARNING_DAYS = 14


def _status_for_pct(pct: float | None) -> str:
    if pct is None:
        return "ok"
    if pct > OVER_BUDGET_THRESHOLD * 100:
        return "over"
    if pct >= WARNING_BUDGET_THRESHOLD * 100:
        return "warning"
    return "ok"


def pot_usage(pot: models.Pot, transactions: list[models.Transaction], today: date) -> PotUsage:
    """How "used up" a pot is, measured the way that's meaningful for its type:
    this calendar month for a monthly-limit budget, the whole grant/budget lifetime
    for a grant/reserve, or progress toward target for a savings goal."""
    approved = [t for t in transactions if t.pot_id == pot.id and t.status == models.TransactionStatus.approved]

    if pot.type == models.PotType.savings_goal:
        used = pot.current_balance
        limit = pot.target_amount
        pct = (used / limit * 100) if limit else None
        return PotUsage(pot.id, pot.name, "goal", used, limit, pct, _status_for_pct(None) if pct is None else _goal_status(pct))

    if pot.type == models.PotType.reserve:
        # A reserve builds UP toward a cushion, not down like a budget — "used" here
        # means "how much of the target cushion is currently held."
        used = pot.current_balance
        limit = pot.budget_or_grant_amount
        pct = (used / limit * 100) if limit else None
        return PotUsage(pot.id, pot.name, "reserve", used, limit, pct, "ok")

    if pot.monthly_limit:
        month_spent = sum(
            t.amount for t in approved if t.date.year == today.year and t.date.month == today.month
        )
        pct = month_spent / pot.monthly_limit * 100 if pot.monthly_limit else None
        return PotUsage(pot.id, pot.name, "this month", month_spent, pot.monthly_limit, pct, _status_for_pct(pct))

    if pot.budget_or_grant_amount:
        spent = pot.budget_or_grant_amount - pot.current_balance
        pct = spent / pot.budget_or_grant_amount * 100
        return PotUsage(pot.id, pot.name, "lifetime", spent, pot.budget_or_grant_amount, pct, _status_for_pct(pct))

    return PotUsage(pot.id, pot.name, "lifetime", 0.0, None, None, "ok")


def _goal_status(pct: float) -> str:
    # For goals, "over" (100%+) is good news, not a problem — only flag behind-pace via find_issues.
    return "ok"


def _goal_behind_pace(pot: models.Pot, today: date) -> Issue | None:
    if pot.type != models.PotType.savings_goal or not pot.target_amount or not pot.deadline:
        return None
    if today >= pot.deadline:
        return None
    total_days = (pot.deadline - (pot.start_date or today)).days
    if total_days <= 0:
        return None
    elapsed_days = (today - (pot.start_date or today)).days
    expected_fraction = min(max(elapsed_days / total_days, 0.0), 1.0)
    actual_fraction = min(pot.current_balance / pot.target_amount, 1.5)
    if expected_fraction - actual_fraction >= GOAL_BEHIND_PACE_MARGIN:
        shortfall = expected_fraction * pot.target_amount - pot.current_balance
        return Issue(
            pot_id=pot.id,
            pot_name=pot.name,
            kind="goal_behind_pace",
            detail=(
                f"At this pace, '{pot.name}' will miss its {pot.deadline.strftime('%m/%d/%Y')} deadline — "
                f"about ${shortfall:,.2f} behind where it needs to be today."
            ),
        )
    return None


def _status_phrase(t: models.Transaction) -> str:
    """A pending expense is still actionable — flagging that distinctly (vs. one
    that already went through) is what lets the AI say e.g. "this $1,100 laptop is
    waiting for approval and breaks the grant's rules" instead of just describing
    history after the fact."""
    return "is waiting for approval and was" if t.status == models.TransactionStatus.pending else "was"


def _category_violations(pot: models.Pot, transactions: list[models.Transaction]) -> list[Issue]:
    issues: list[Issue] = []
    for t in transactions:
        if t.pot_id != pot.id or t.status == models.TransactionStatus.rejected:
            continue
        status_phrase = _status_phrase(t)
        category = (t.category or "").strip().lower()
        if pot.disallowed_categories and category in {c.lower() for c in pot.disallowed_categories}:
            issues.append(
                Issue(
                    pot.id, pot.name, "disallowed_category",
                    f"{t.merchant} (${t.amount:,.2f}, category '{t.category}') {status_phrase} charged to "
                    f"'{pot.name}', but that category isn't allowed for this pot.",
                    transaction_id=t.id,
                )
            )
        elif pot.allowed_categories and category not in {c.lower() for c in pot.allowed_categories}:
            issues.append(
                Issue(
                    pot.id, pot.name, "disallowed_category",
                    f"{t.merchant} (${t.amount:,.2f}, category '{t.category}') {status_phrase} charged to "
                    f"'{pot.name}', which only allows: {', '.join(pot.allowed_categories)}.",
                    transaction_id=t.id,
                )
            )
        if pot.end_date and t.date > pot.end_date:
            issues.append(
                Issue(
                    pot.id, pot.name, "outside_grant_window",
                    f"{t.merchant} (${t.amount:,.2f}) on {t.date.strftime('%m/%d/%Y')} {status_phrase} after "
                    f"'{pot.name}' ended ({pot.end_date.strftime('%m/%d/%Y')}).",
                    transaction_id=t.id,
                )
            )
        if pot.start_date and t.date < pot.start_date:
            issues.append(
                Issue(
                    pot.id, pot.name, "outside_grant_window",
                    f"{t.merchant} (${t.amount:,.2f}) on {t.date.strftime('%m/%d/%Y')} {status_phrase} before "
                    f"'{pot.name}' started ({pot.start_date.strftime('%m/%d/%Y')}).",
                    transaction_id=t.id,
                )
            )
    return issues


def _last_month_bounds(today: date) -> tuple[int, int]:
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return year, month


def _last_month_overspend(pot: models.Pot, transactions: list[models.Transaction]) -> Issue | None:
    """Catches a budget blown last month, not just a live over-this-month status —
    a monthly cap that was already exceeded is still worth surfacing early in a new
    month, even though the live pot card now shows a fresh (lower) this-month total."""
    if not pot.monthly_limit:
        return None
    year, month = _last_month_bounds(date.today())
    spent = sum(
        t.amount
        for t in transactions
        if t.pot_id == pot.id
        and t.status == models.TransactionStatus.approved
        and t.date.year == year
        and t.date.month == month
    )
    if spent > pot.monthly_limit:
        pct = spent / pot.monthly_limit * 100
        return Issue(
            pot.id, pot.name, "over_budget",
            f"'{pot.name}' went over budget last month: ${spent:,.2f} spent of "
            f"${pot.monthly_limit:,.2f} ({pct:.0f}%).",
        )
    return None


def _reserve_shortfall(pot: models.Pot, transactions: list[models.Transaction], today: date) -> Issue | None:
    """For a reserve pot, `monthly_limit` is read as "the amount that should be set aside
    this month" (e.g. this month's sales-tax liability) rather than a spending cap — the
    only field the data model has for a recurring target. If less than 80% of that has
    actually been deposited this month, the reserve is falling short."""
    if pot.type != models.PotType.reserve or not pot.monthly_limit:
        return None
    month_deposits = sum(
        t.amount
        for t in transactions
        if t.pot_id == pot.id
        and t.status == models.TransactionStatus.approved
        and t.date.year == today.year
        and t.date.month == today.month
    )
    if month_deposits < pot.monthly_limit * 0.8:
        return Issue(
            pot.id, pot.name, "reserve_shortfall",
            f"'{pot.name}' has only received ${month_deposits:,.2f} of the ${pot.monthly_limit:,.2f} "
            f"expected this month.",
        )
    return None


def payroll_coverage(
    pot: models.Pot,
    transactions: list[models.Transaction],
    recurring_charges: list[models.RecurringCharge],
    today: date,
) -> dict | None:
    """Pure math, shared by the Rules Checker's payroll_not_covered check and the
    Analyst's check_payroll_coverage tool. Not every workspace has a pot named
    "Payroll" (e.g. groups never do) — returns None when there's nothing to check.

    expected_amount comes from an active recurring charge on this pot if one
    exists (the known, scheduled payroll run), else the average of this pot's
    own past transactions (the best guess available from history alone)."""
    if pot.type != models.PotType.spending or "payroll" not in pot.name.lower():
        return None

    own_charges = [c for c in recurring_charges if c.pot_id == pot.id and c.active]
    if own_charges:
        expected_amount = max(c.amount for c in own_charges)
        source = "its scheduled recurring charge"
    else:
        past = [
            t.amount
            for t in transactions
            if t.pot_id == pot.id and t.status == models.TransactionStatus.approved
        ]
        if not past:
            return None
        expected_amount = sum(past) / len(past)
        source = "its own transaction history"

    covered = pot.current_balance >= expected_amount
    return {
        "pot_name": pot.name,
        "current_balance": round(pot.current_balance, 2),
        "expected_amount": round(expected_amount, 2),
        "covered": covered,
        "shortfall": round(max(expected_amount - pot.current_balance, 0.0), 2),
        "source": source,
    }


def _payroll_shortfall(
    pot: models.Pot, transactions: list[models.Transaction], recurring_charges: list[models.RecurringCharge], today: date
) -> Issue | None:
    coverage = payroll_coverage(pot, transactions, recurring_charges, today)
    if coverage is None or coverage["covered"]:
        return None
    return Issue(
        pot.id, pot.name, "payroll_not_covered",
        f"'{pot.name}' has ${coverage['current_balance']:,.2f} left, but the next payroll run "
        f"(based on {coverage['source']}) is about ${coverage['expected_amount']:,.2f} — "
        f"short by ${coverage['shortfall']:,.2f}.",
    )


def _report_deadline_approaching(pot: models.Pot, today: date) -> list[Issue]:
    if not pot.report_deadlines:
        return []
    issues = []
    for entry in pot.report_deadlines:
        try:
            deadline = date.fromisoformat(entry["date"])
        except (KeyError, ValueError, TypeError):
            continue
        days_left = (deadline - today).days
        if 0 <= days_left <= REPORT_DEADLINE_WARNING_DAYS:
            description = entry.get("description") or "a report"
            issues.append(
                Issue(
                    pot.id, pot.name, "report_deadline_approaching",
                    f"'{pot.name}' owes {description} by {deadline.strftime('%m/%d/%Y')} "
                    f"({days_left} day{'s' if days_left != 1 else ''} away).",
                )
            )
    return issues


def find_issues(
    pots: list[models.Pot],
    transactions: list[models.Transaction],
    today: date,
    recurring_charges: list[models.RecurringCharge] | None = None,
) -> list[Issue]:
    recurring_charges = recurring_charges or []
    issues: list[Issue] = []
    for pot in pots:
        usage = pot_usage(pot, transactions, today)
        if usage.status == "over" and pot.type not in (models.PotType.savings_goal, models.PotType.reserve):
            issues.append(
                Issue(
                    pot.id, pot.name, "over_budget",
                    f"'{pot.name}' is over budget: ${usage.used:,.2f} used of ${usage.limit:,.2f} {usage.period}.",
                )
            )
        elif pot.type not in (models.PotType.savings_goal, models.PotType.reserve):
            last_month_issue = _last_month_overspend(pot, transactions)
            if last_month_issue:
                issues.append(last_month_issue)
        behind = _goal_behind_pace(pot, today)
        if behind:
            issues.append(behind)
        shortfall = _reserve_shortfall(pot, transactions, today)
        if shortfall:
            issues.append(shortfall)
        payroll_issue = _payroll_shortfall(pot, transactions, recurring_charges, today)
        if payroll_issue:
            issues.append(payroll_issue)
        issues.extend(_category_violations(pot, transactions))
        issues.extend(_report_deadline_approaching(pot, today))
    return issues
