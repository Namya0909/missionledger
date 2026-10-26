"""The Rules Checker catches each of the 3 mistakes planted in the seed data —
calls rules.find_issues() directly against the real seeded pots/transactions, no
API layer and no AI involved (find_issues() is pure Python; see rules.py)."""

from datetime import date

import models
from rules import find_issues


def _workspace_id(db_session, name: str) -> int:
    ws = db_session.query(models.Workspace).filter_by(name=name).first()
    assert ws is not None, f"expected a seeded workspace named {name!r}"
    return ws.id


def _issues_for(db_session, workspace_name: str) -> list:
    ws_id = _workspace_id(db_session, workspace_name)
    pots = db_session.query(models.Pot).filter_by(workspace_id=ws_id).all()
    transactions = db_session.query(models.Transaction).filter_by(workspace_id=ws_id).all()
    recurring = db_session.query(models.RecurringCharge).filter_by(workspace_id=ws_id).all()
    return find_issues(pots, transactions, date.today(), recurring)


def test_mistake_1_group_goal_behind_pace(db_session):
    """Oak Street House: the "Weekend Trip" savings goal is deliberately
    underfunded relative to its deadline."""
    issues = _issues_for(db_session, "Oak Street House")
    goal_issues = [i for i in issues if i.kind == "goal_behind_pace" and i.pot_name == "Weekend Trip"]
    assert goal_issues, f"expected a goal_behind_pace issue on 'Weekend Trip', got kinds: {[i.kind for i in issues]}"


def test_mistake_2_nonprofit_disallowed_categories(db_session):
    """Elm Street Community Food Bank: three transactions were planted that
    violate their grant's allowed/disallowed category rules (an Equipment and a
    Salaries purchase on the Hunger Relief Grant, which disallows both, and an
    Office Supplies purchase on the City Youth Meals Grant, which only allows
    "Youth Meals")."""
    issues = _issues_for(db_session, "Elm Street Community Food Bank")
    category_issues = [i for i in issues if i.kind == "disallowed_category"]
    assert len(category_issues) >= 3, (
        f"expected at least 3 disallowed_category issues (Equipment + Salaries on Hunger "
        f"Relief Grant, Office Supplies on City Youth Meals Grant), got {len(category_issues)}: "
        f"{[(i.pot_name, i.detail) for i in category_issues]}"
    )
    flagged_pots = {i.pot_name for i in category_issues}
    assert "Hunger Relief Grant" in flagged_pots
    assert "City Youth Meals Grant" in flagged_pots


def test_mistake_3_business_reserve_shortfall(db_session):
    """Corner Coffee Co.: the Sales Tax Savings reserve only has ~40% of what's
    actually owed this month deposited into it."""
    issues = _issues_for(db_session, "Corner Coffee Co.")
    shortfalls = [i for i in issues if i.kind == "reserve_shortfall" and i.pot_name == "Sales Tax Savings"]
    assert shortfalls, f"expected a reserve_shortfall issue on 'Sales Tax Savings', got kinds: {[i.kind for i in issues]}"


def test_no_false_positives_on_healthy_pots(db_session):
    """Pots that were NOT deliberately broken shouldn't show up as issues —
    e.g. Corner Coffee Co.'s Payroll and Operating pots are fully funded this
    month by design."""
    issues = _issues_for(db_session, "Corner Coffee Co.")
    flagged_pots = {i.pot_name for i in issues}
    assert "Payroll" not in flagged_pots
    assert "Operating" not in flagged_pots
