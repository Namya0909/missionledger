"""Expense-splitting and debt-simplification math for groups — pure Python, no AI
ever touches these numbers (per the user's explicit instruction).

A pot with a split_method is shared: whoever logs a transaction on it paid for it,
and every member owes their fair share of it back (equal / by income / custom
percentages). Net balances across every shared pot are then simplified into the
smallest set of "who pays whom" transfers that settles everyone up.
"""

from dataclasses import dataclass, field

import models

ROUNDING_EPSILON = 0.01


def fair_share_fractions(
    pot: models.Pot, member_user_ids: list[int], incomes: dict[int, float]
) -> dict[int, float]:
    """{user_id: fraction of this pot's cost they owe}, summing to ~1.0."""
    n = len(member_user_ids)
    if n == 0:
        return {}

    if pot.split_method == models.SplitMethod.custom and pot.custom_shares:
        return {int(uid): frac for uid, frac in pot.custom_shares.items() if int(uid) in member_user_ids}

    if pot.split_method == models.SplitMethod.income:
        total_income = sum(incomes.get(uid) or 0 for uid in member_user_ids)
        if total_income > 0:
            return {uid: (incomes.get(uid) or 0) / total_income for uid in member_user_ids}
        # Nobody has a recorded income yet — fall back to equal rather than divide by zero.

    return {uid: 1 / n for uid in member_user_ids}


@dataclass
class SettleUp:
    # user_id -> net balance: positive = owed money by the group, negative = owes the group
    balances: dict[int, float] = field(default_factory=dict)
    # minimal transfers that would bring every balance to zero
    transfers: list[dict] = field(default_factory=list)


def compute_settle_up(
    pots: list[models.Pot],
    transactions: list[models.Transaction],
    member_user_ids: list[int],
    incomes: dict[int, float],
    settlements: list[models.Settlement] | None = None,
) -> SettleUp:
    balances = {uid: 0.0 for uid in member_user_ids}

    for pot in pots:
        if pot.split_method is None:
            continue  # not a shared pot — doesn't factor into who-owes-whom
        shares = fair_share_fractions(pot, member_user_ids, incomes)
        for t in transactions:
            if t.pot_id != pot.id or t.status != models.TransactionStatus.approved:
                continue
            for uid, frac in shares.items():
                balances[uid] = balances.get(uid, 0.0) - t.amount * frac
            if t.created_by_user_id in balances:
                balances[t.created_by_user_id] += t.amount

    # A real payment someone already made settles part of what they owed — paying
    # credits the payer and debits the receiver, same direction as a debt transfer.
    for s in settlements or []:
        if s.from_user_id in balances:
            balances[s.from_user_id] += s.amount
        if s.to_user_id in balances:
            balances[s.to_user_id] -= s.amount

    transfers = _simplify(balances)
    return SettleUp(balances={uid: round(b, 2) for uid, b in balances.items()}, transfers=transfers)


def _simplify(balances: dict[int, float]) -> list[dict]:
    """Greedy largest-creditor-vs-largest-debtor matching — a simple, well-known way
    to settle a group of balances in close to the minimum number of transfers."""
    creditors = sorted([[uid, bal] for uid, bal in balances.items() if bal > ROUNDING_EPSILON], key=lambda x: -x[1])
    debtors = sorted([[uid, -bal] for uid, bal in balances.items() if bal < -ROUNDING_EPSILON], key=lambda x: -x[1])

    transfers = []
    ci = di = 0
    while ci < len(creditors) and di < len(debtors):
        amount = min(creditors[ci][1], debtors[di][1])
        if amount > ROUNDING_EPSILON:
            transfers.append({"from_user_id": debtors[di][0], "to_user_id": creditors[ci][0], "amount": round(amount, 2)})
        creditors[ci][1] -= amount
        debtors[di][1] -= amount
        if creditors[ci][1] <= ROUNDING_EPSILON:
            ci += 1
        if debtors[di][1] <= ROUNDING_EPSILON:
            di += 1

    return transfers
