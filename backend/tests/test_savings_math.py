"""The savings-math feasibility calculation is right for 5 different examples.
compute_savings_analysis() is pure Python (no AI, no DB) — see ai/setup_agent.py.

Dates are computed relative to the real `date.today()` at test-run time (not
frozen), so these assertions hold no matter what day the suite actually runs on.
"""

from datetime import date, timedelta

from ai.setup_agent import DAYS_PER_MONTH, SetupCollected, compute_savings_analysis


def _goal_date(days_out: int) -> str:
    return (date.today() + timedelta(days=days_out)).isoformat()


def test_example_1_easily_feasible():
    # $1,200 goal, 200 days out (~6.57 months), can afford $300/mo — comfortably feasible.
    analysis = compute_savings_analysis(
        SetupCollected(goal_amount=1200, goal_date=_goal_date(200), monthly_capacity=300)
    )
    months_left = round(200 / DAYS_PER_MONTH, 2)
    required_monthly = round(1200 / months_left, 2)
    assert analysis.months_left == months_left
    assert analysis.required_monthly == required_monthly
    assert analysis.feasible is True
    assert analysis.shortfall_per_month == 0.0
    assert analysis.options == []


def test_example_2_exactly_at_capacity():
    # Goal sized so required_monthly lands exactly on what they can afford.
    months_left = round(100 / DAYS_PER_MONTH, 2)
    capacity = 150.0
    goal_amount = round(capacity * months_left, 2)
    analysis = compute_savings_analysis(
        SetupCollected(goal_amount=goal_amount, goal_date=_goal_date(100), monthly_capacity=capacity)
    )
    assert analysis.feasible is True
    assert analysis.shortfall_per_month == 0.0
    assert analysis.required_monthly <= capacity


def test_example_3_infeasible_with_shortfall():
    # $5,000 by ~June (reproduces the "Vacation Fund" example from the app):
    # ~7.2 months out, $400/month capacity -> short by a real, specific amount.
    months_left = round(219 / DAYS_PER_MONTH, 2)  # ~7.19 months
    analysis = compute_savings_analysis(
        SetupCollected(goal_amount=5000, goal_date=_goal_date(219), monthly_capacity=400)
    )
    required_monthly = round(5000 / months_left, 2)
    assert analysis.months_left == months_left
    assert analysis.required_monthly == required_monthly
    assert analysis.feasible is False
    expected_shortfall = round(required_monthly - 400, 2)
    assert analysis.shortfall_per_month == expected_shortfall
    assert len(analysis.options) == 3
    # Each option is a real, usable alternative, not just a restatement of the problem.
    assert any("Push the date" in o for o in analysis.options)
    assert any("Lower the goal" in o for o in analysis.options)
    assert any("more per month" in o for o in analysis.options)


def test_example_4_no_capacity_given_is_always_feasible():
    # If they haven't said how much they can save, we can't call it infeasible.
    analysis = compute_savings_analysis(SetupCollected(goal_amount=10_000, goal_date=_goal_date(365)))
    assert analysis.feasible is True
    assert analysis.monthly_capacity is None
    assert analysis.shortfall_per_month is None
    assert analysis.options == []


def test_example_5_missing_goal_returns_none():
    # No goal_amount or no goal_date at all -> nothing to analyze.
    assert compute_savings_analysis(SetupCollected(goal_date=_goal_date(100), monthly_capacity=200)) is None
    assert compute_savings_analysis(SetupCollected(goal_amount=1000, monthly_capacity=200)) is None
