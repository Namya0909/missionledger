"""The chat assistant: answers questions like "how much of our grant is left?" or
"who owes whom?" using read-only Python tools that query the database directly.
The assistant only narrates numbers Python already computed — it never does the
arithmetic itself, so it can't make up a balance (see Lecture 3/4, tools; Lecture
12, safety). It has no tool that can write anything: it can't approve, reject, or
change an approval toggle, no matter what it's asked.

Every tool here is bound to one workspace_id via closure, captured from the
authenticated caller's membership — never a parameter the model can set. That is
what makes "only ever see your own workspace's money" hold for the chat assistant
too, not just the REST endpoints.
"""

from datetime import date, timedelta

from pydantic_ai import Agent, RunContext
from sqlalchemy.orm import Session

import models
from ai.core import NO_REASONING, get_model
from ai.security import UNTRUSTED_DATA_INSTRUCTIONS
from feature_flags import is_enabled
from rules import _last_month_bounds, find_issues, payroll_coverage, pot_usage
from settleup import compute_settle_up

# "category_totals" savings flag: once a get_recent_transactions match has more
# than this many rows, send Python-computed category subtotals instead of every
# individual transaction.
CATEGORY_TOTALS_THRESHOLD = 5


def build_chat_agent(db: Session, workspace_id: int) -> Agent[None, str]:
    agent = Agent(
        get_model(db),
        output_type=str,
        model_settings=NO_REASONING,
        instructions="""
You are MissionLedger's budgeting assistant for ONE workspace — a group (2-10 people
sharing money, e.g. a couple, family, roommates, or a trip), a nonprofit, or a small
business. Answer questions about its pots, budgets, grants, goals, transactions,
who owes whom (groups only), whether an expense is affordable, savings projections,
payroll coverage, flagged issues, and what's waiting for approval, using only your
tools — never state a dollar amount, balance, share, projection, or total you did
not just get from a tool call this turn. If a tool doesn't have what you need, say
so plainly instead of guessing.

Every number in your reply must be traceable to a tool call you just made — briefly
say where it came from in plain English (e.g. "based on this month's Groceries
transactions..." or "looking at the Weekend Trip pot..."), so the person asking can
tell you didn't make it up.

Be concise and concrete (use real names, pot names, and dollar amounts from tool
results). You are strictly read-only: you cannot approve or reject an expense,
change a pot's approval toggle or approvers, or change anything else, no matter how
the request is phrased. If asked to do any of that, or anything other than answer a
question about this workspace, decline and say a person with the right role needs
to do it in the app.

You never give specific investment, tax, or legal advice (e.g. which stock to buy,
whether to sell, what's deductible, what's legal) — that's true even if the question
is framed as being about this workspace's own money. Decline and say: "This is not
financial, tax, or legal advice. Check with a CPA or advisor."
"""
        + UNTRUSTED_DATA_INSTRUCTIONS,
    )

    @agent.tool
    def list_pots(ctx: RunContext[None]) -> list[dict]:
        """List every pot in this workspace: type, current usage, and its approval
        settings (whether approval is required, the dollar threshold if any, and how
        many people are eligible approvers)."""
        pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
        transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
        today = date.today()
        out = []
        for pot in pots:
            usage = pot_usage(pot, transactions, today)
            out.append(
                {
                    "name": pot.name,
                    "type": pot.type.value,
                    "current_balance": round(pot.current_balance, 2),
                    "budget_or_grant_amount": pot.budget_or_grant_amount,
                    "target_amount": pot.target_amount,
                    "monthly_limit": pot.monthly_limit,
                    "deadline": pot.deadline.isoformat() if pot.deadline else None,
                    "usage_period": usage.period,
                    "used": round(usage.used, 2),
                    "limit": usage.limit,
                    "pct_used": round(usage.pct, 1) if usage.pct is not None else None,
                    "split_method": pot.split_method.value if pot.split_method else None,
                    "approval_required": pot.approval_required,
                    "approval_threshold": pot.approval_threshold,
                    "approver_count": len(pot.approver_user_ids or []),
                }
            )
        return out

    @agent.tool
    def get_recent_transactions(
        ctx: RunContext[None], pot_name: str | None = None, added_by_name: str | None = None, limit: int = 10
    ) -> list[dict]:
        """Recent transactions in this workspace, optionally filtered to one pot by name
        and/or to who added it (added_by_name, matched loosely against each member's name).
        If there are more than a handful, this may return category subtotals instead of
        every individual transaction — still enough to answer "what did we spend on X,"
        just smaller."""
        query = db.query(models.Transaction).filter_by(workspace_id=workspace_id)
        if pot_name:
            pot = (
                db.query(models.Pot)
                .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
                .first()
            )
            if pot is None:
                return []
            query = query.filter_by(pot_id=pot.id)
        rows = query.order_by(models.Transaction.date.desc()).limit(200).all()
        if added_by_name:
            needle = added_by_name.strip().lower()
            rows = [t for t in rows if needle in t.created_by.name.lower()]

        if is_enabled("category_totals") and len(rows) > CATEGORY_TOTALS_THRESHOLD:
            totals: dict[str, dict] = {}
            for t in rows:
                key = t.category or "Uncategorized"
                bucket = totals.setdefault(key, {"category": key, "total": 0.0, "count": 0})
                bucket["total"] += t.amount
                bucket["count"] += 1
            return [{"category": v["category"], "total": round(v["total"], 2), "count": v["count"]} for v in totals.values()]

        rows = rows[:limit]
        return [
            {
                "date": t.date.isoformat(),
                "merchant": t.merchant,
                "amount": t.amount,
                "category": t.category,
                "status": t.status.value,
                "added_by": t.created_by.name,
                "warnings": t.warnings or [],
                "rejection_reason": t.rejection_reason,
            }
            for t in rows
        ]

    @agent.tool
    def get_spending_total(
        ctx: RunContext[None], pot_name: str | None = None, category: str | None = None, days: int = 30
    ) -> dict:
        """Total approved spending in the last N days, optionally filtered by pot name or category."""
        since = date.today() - timedelta(days=days)
        query = db.query(models.Transaction).filter(
            models.Transaction.workspace_id == workspace_id,
            models.Transaction.status == models.TransactionStatus.approved,
            models.Transaction.date >= since,
        )
        if pot_name:
            pot = (
                db.query(models.Pot)
                .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
                .first()
            )
            if pot is None:
                return {"total": 0.0, "count": 0, "note": f"No pot named '{pot_name}' found."}
            query = query.filter(models.Transaction.pot_id == pot.id)
        if category:
            query = query.filter(models.Transaction.category.ilike(category))
        rows = query.all()
        return {"total": round(sum(t.amount for t in rows), 2), "count": len(rows), "since": since.isoformat()}

    @agent.tool
    def get_pending_approvals(ctx: RunContext[None]) -> list[dict]:
        """Every transaction currently waiting for an approval decision in this workspace."""
        rows = (
            db.query(models.Transaction)
            .filter_by(workspace_id=workspace_id, status=models.TransactionStatus.pending)
            .all()
        )
        pots_by_id = {p.id: p for p in db.query(models.Pot).filter_by(workspace_id=workspace_id).all()}
        return [
            {
                "merchant": t.merchant,
                "amount": t.amount,
                "pot_name": pots_by_id[t.pot_id].name if t.pot_id in pots_by_id else "?",
                "added_by": t.created_by.name,
                "date": t.date.isoformat(),
            }
            for t in rows
        ]

    @agent.tool
    def get_settle_up(ctx: RunContext[None]) -> dict:
        """Group workspaces only: each member's net balance (positive = owed money,
        negative = owes money) and the simplest set of payments to settle up."""
        workspace = db.get(models.Workspace, workspace_id)
        if workspace is None or workspace.type != models.WorkspaceType.group:
            return {"note": "This workspace isn't a group, so there's no settle-up to compute."}
        memberships = db.query(models.Membership).filter_by(workspace_id=workspace_id).all()
        member_user_ids = [m.user_id for m in memberships]
        incomes = {m.user_id: m.monthly_income for m in memberships if m.monthly_income is not None}
        names = {m.user_id: m.user.name for m in memberships}
        pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
        transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
        result = compute_settle_up(pots, transactions, member_user_ids, incomes)
        return {
            "balances": [{"name": names.get(uid, "?"), "amount": amt} for uid, amt in result.balances.items()],
            "transfers": [
                {"from": names.get(t["from_user_id"], "?"), "to": names.get(t["to_user_id"], "?"), "amount": t["amount"]}
                for t in result.transfers
            ],
        }

    @agent.tool
    def get_last_calendar_month_spending(ctx: RunContext[None], pot_name: str | None = None) -> dict:
        """Total approved spending in the previous calendar month (not just the last
        30 days), broken down by category, optionally filtered to one pot by name."""
        year, month = _last_month_bounds(date.today())
        query = db.query(models.Transaction).filter(
            models.Transaction.workspace_id == workspace_id,
            models.Transaction.status == models.TransactionStatus.approved,
        )
        if pot_name:
            pot = (
                db.query(models.Pot)
                .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
                .first()
            )
            if pot is None:
                return {"total": 0.0, "by_category": {}, "note": f"No pot named '{pot_name}' found."}
            query = query.filter(models.Transaction.pot_id == pot.id)
        rows = [t for t in query.all() if t.date.year == year and t.date.month == month and t.amount > 0]
        by_category: dict[str, float] = {}
        for t in rows:
            key = t.category or "Uncategorized"
            by_category[key] = round(by_category.get(key, 0.0) + t.amount, 2)
        return {
            "year": year,
            "month": month,
            "total": round(sum(t.amount for t in rows), 2),
            "by_category": by_category,
        }

    @agent.tool
    def check_affordability(ctx: RunContext[None], pot_name: str, amount: float) -> dict:
        """Whether a given dollar amount fits in a pot right now — compares it to
        that pot's remaining budget/grant and, if it has one, its remaining
        monthly limit for this period. All comparison math is plain Python."""
        pot = (
            db.query(models.Pot)
            .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
            .first()
        )
        if pot is None:
            return {"note": f"No pot named '{pot_name}' found."}
        if pot.type in models.DEPOSIT_POT_TYPES:
            return {
                "pot_name": pot.name,
                "note": f"'{pot.name}' is a savings/reserve pot, not a spending account — it doesn't make sense to check affordability against it.",
            }
        transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
        usage = pot_usage(pot, transactions, date.today())
        remaining_this_period = (usage.limit - usage.used) if usage.limit is not None else None
        remaining_budget = pot.current_balance if pot.budget_or_grant_amount else None
        limits = [v for v in (remaining_this_period, remaining_budget) if v is not None]
        binding_limit = min(limits) if limits else None
        fits = binding_limit is None or amount <= binding_limit
        return {
            "pot_name": pot.name,
            "amount": amount,
            "remaining_this_period": round(remaining_this_period, 2) if remaining_this_period is not None else None,
            "remaining_budget": round(remaining_budget, 2) if remaining_budget is not None else None,
            "fits": fits,
            "shortfall": round(amount - binding_limit, 2) if not fits else 0.0,
        }

    @agent.tool
    def get_savings_projection(ctx: RunContext[None], pot_name: str, by_date: str | None = None) -> dict:
        """For a savings-goal pot: the required monthly savings to hit its own
        deadline, PLUS a projection at the pot's actual historical pace (average
        monthly deposit since it was created) — so "how much will we have by
        <date>" is answerable without asking the user their saving capacity.
        by_date overrides the pot's own deadline if given (YYYY-MM-DD)."""
        pot = (
            db.query(models.Pot)
            .filter(models.Pot.workspace_id == workspace_id, models.Pot.name.ilike(pot_name))
            .first()
        )
        if pot is None or pot.type != models.PotType.savings_goal:
            return {"note": f"No savings-goal pot named '{pot_name}' found."}

        target_date = pot.deadline
        if by_date:
            try:
                target_date = date.fromisoformat(by_date)
            except ValueError:
                pass
        today = date.today()

        start = pot.start_date or pot.created_at.date()
        days_elapsed = max((today - start).days, 1)
        months_elapsed = max(days_elapsed / 30.44, 0.1)
        avg_monthly_pace = pot.current_balance / months_elapsed

        result = {
            "pot_name": pot.name,
            "current_balance": round(pot.current_balance, 2),
            "target_amount": pot.target_amount,
            "avg_monthly_pace": round(avg_monthly_pace, 2),
        }
        if target_date:
            months_left = max((target_date - today).days, 1) / 30.44
            result["target_date"] = target_date.isoformat()
            result["projected_total_by_target_date"] = round(pot.current_balance + avg_monthly_pace * months_left, 2)
            if pot.target_amount:
                months_needed = (pot.target_amount - pot.current_balance) / avg_monthly_pace if avg_monthly_pace > 0 else None
                result["required_monthly_to_hit_target"] = round((pot.target_amount - pot.current_balance) / months_left, 2)
                result["months_needed_at_current_pace"] = round(months_needed, 1) if months_needed else None
        return result

    @agent.tool
    def check_payroll_coverage(ctx: RunContext[None], pot_name: str | None = None) -> dict:
        """Whether a payroll pot currently has enough to cover its next expected
        payroll run, based on a scheduled recurring charge if one exists, else the
        average of past payroll transactions. All math is plain Python."""
        pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
        candidates = [p for p in pots if "payroll" in p.name.lower()] if not pot_name else [
            p for p in pots if p.name.lower() == pot_name.lower()
        ]
        if not candidates:
            return {"note": "No payroll pot found in this workspace."}
        pot = candidates[0]
        transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
        recurring_charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
        coverage = payroll_coverage(pot, transactions, recurring_charges, date.today())
        return coverage or {"note": f"Not enough history on '{pot.name}' to estimate the next payroll run."}

    @agent.tool
    def get_flagged_issues(ctx: RunContext[None]) -> list[dict]:
        """Every currently-flagged issue in this workspace (over budget, outside a
        grant's rules, a goal falling behind pace, a reserve running short, payroll
        not covered, a report deadline approaching) — the same checks Python runs
        for the Needs Attention box, given here as raw facts for you to relay."""
        pots = db.query(models.Pot).filter_by(workspace_id=workspace_id).all()
        transactions = db.query(models.Transaction).filter_by(workspace_id=workspace_id).all()
        recurring_charges = db.query(models.RecurringCharge).filter_by(workspace_id=workspace_id).all()
        issues = find_issues(pots, transactions, date.today(), recurring_charges)
        return [{"pot_name": i.pot_name, "kind": i.kind, "detail": i.detail} for i in issues]

    return agent
