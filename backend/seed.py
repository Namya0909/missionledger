"""Creates the three demo workspaces (group, nonprofit, business) with demo users
(password demo1234) and ~3 months of realistic transaction history, including a
few deliberate mistakes so the rules engine (rules.py) and the AI "Needs attention"
explainer have something real to catch.

Runs once, automatically, on startup (see main.py). Idempotent: if the demo users
already exist, it does nothing, so it never duplicates data or clobbers anything a
tester has since changed.
"""

import random
from datetime import date, timedelta

import models
from auth import hash_password, hash_security_answer
from database import SessionLocal
from permissions import needs_approval

DEMO_PASSWORD = "demo1234"
RNG_SEED = 20261025

# Every demo account uses the same 3 security questions/answers, so the frontend's
# one-click "Try a demo" buttons can complete both login steps without per-user
# special-casing. Kept in sync with LoginPage.jsx's DEMO_SECURITY_ANSWERS.
DEMO_SECURITY_ANSWERS = {"color": "Blue", "pet": "Dog", "food": "Pizza"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _apply(pot: models.Pot, amount: float) -> None:
    if pot.type in models.DEPOSIT_POT_TYPES:
        pot.current_balance += amount
    else:
        pot.current_balance -= amount


def _month_bounds(months_back: int, today: date) -> tuple[date, date]:
    y, m = today.year, today.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    start = date(y, m, 1)
    next_start = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    end = next_start - timedelta(days=1)
    if months_back == 0:
        end = min(end, today)
    return start, end


def _days_in(start: date, end: date) -> int:
    return max((end - start).days + 1, 1)


def _random_dates(rng: random.Random, start: date, end: date, count: int) -> list[date]:
    span = (end - start).days
    if span <= 0 or count <= 0:
        return [start] * max(count, 0)
    return sorted(start + timedelta(days=rng.randint(0, span)) for _ in range(count))


def _make_user(db, name: str, email: str) -> models.User:
    user = models.User(name=name, email=email, password_hash=hash_password(DEMO_PASSWORD))
    db.add(user)
    db.flush()
    for key, answer in DEMO_SECURITY_ANSWERS.items():
        db.add(models.SecurityAnswer(user_id=user.id, question_key=key, answer_hash=hash_security_answer(answer)))
    return user


def _make_workspace(
    db, name: str, type_: models.WorkspaceType, *, tax_pack_enabled: bool = False, state: str | None = None
) -> models.Workspace:
    ws = models.Workspace(name=name, type=type_, tax_pack_enabled=tax_pack_enabled, state=state)
    db.add(ws)
    db.flush()
    return ws


def _member(db, ws: models.Workspace, user: models.User, role: models.Role, monthly_income: float | None = None) -> None:
    db.add(models.Membership(workspace_id=ws.id, user_id=user.id, role=role, monthly_income=monthly_income))


def _make_pot(db, ws: models.Workspace, **kwargs) -> models.Pot:
    pot = models.Pot(workspace_id=ws.id, **kwargs)
    pot.current_balance = 0.0 if pot.type in models.DEPOSIT_POT_TYPES else (pot.budget_or_grant_amount or 0.0)
    db.add(pot)
    db.flush()
    return pot


def _txn(
    db,
    ws: models.Workspace,
    pot: models.Pot,
    *,
    date_: date,
    merchant: str,
    amount: float,
    category: str,
    created_by: models.User,
    force_pending: bool = False,
    reject_with: str | None = None,
) -> models.Transaction:
    """Resolves status from the pot's OWN approval settings, like the real API does:
    - not required, or under threshold -> auto-approved
    - required and over threshold -> approved by the first eligible approver who
      isn't the creator (simulating "a teammate already signed off"), or left
      pending if nobody else could approve it yet
    `force_pending` keeps a transaction pending regardless, for demo transactions
    meant to show up on the Approvals page / Needs Attention box right now.
    `reject_with` instead marks it rejected with that reason.
    """
    requires = True if force_pending else needs_approval(pot, amount)
    approved_by_id = None
    rejection_reason = None

    if reject_with:
        status = models.TransactionStatus.rejected
        rejection_reason = reject_with
    elif not requires:
        status = models.TransactionStatus.approved
    elif force_pending:
        status = models.TransactionStatus.pending
    else:
        other_approvers = [uid for uid in (pot.approver_user_ids or []) if uid != created_by.id]
        if other_approvers:
            status = models.TransactionStatus.approved
            approved_by_id = other_approvers[0]
        else:
            status = models.TransactionStatus.pending

    t = models.Transaction(
        workspace_id=ws.id,
        pot_id=pot.id,
        date=date_,
        merchant=merchant,
        amount=round(amount, 2),
        category=category,
        status=status,
        source=models.TransactionSource.typed,
        warnings=[],
        rejection_reason=rejection_reason,
        created_by_user_id=created_by.id,
        approved_by_user_id=approved_by_id,
    )
    db.add(t)
    if status == models.TransactionStatus.approved:
        _apply(pot, t.amount)
    return t


# ---------------------------------------------------------------------------
# 1. Group — "Oak Street House"
# ---------------------------------------------------------------------------

def _seed_group(db, rng: random.Random, today: date) -> None:
    ws = _make_workspace(db, "Oak Street House", models.WorkspaceType.group)
    maya = _make_user(db, "Maya Chen", "maya@demo.org")
    josh = _make_user(db, "Josh Rivera", "josh@demo.org")
    sam = _make_user(db, "Sam Patel", "sam@demo.org")
    lena = _make_user(db, "Lena Kowalski", "lena@demo.org")
    roommates = [maya, josh, sam, lena]

    # One admin is enough for a 4-person house; incomes power the "split by income" pot.
    _member(db, ws, maya, models.Role.admin, monthly_income=6000)
    _member(db, ws, josh, models.Role.member, monthly_income=5000)
    _member(db, ws, sam, models.Role.member, monthly_income=3000)
    _member(db, ws, lena, models.Role.member, monthly_income=2000)

    m2 = _month_bounds(2, today)
    m1 = _month_bounds(1, today)
    m0 = _month_bounds(0, today)

    # Approval is off everywhere except the trip goal over $200 (per spec) — so these
    # three need no approver list at all.
    rent = _make_pot(db, ws, name="Rent", type=models.PotType.spending,
                      budget_or_grant_amount=3200, monthly_limit=3200,
                      split_method=models.SplitMethod.equal, approval_required=False)
    utilities = _make_pot(db, ws, name="Utilities", type=models.PotType.spending,
                           budget_or_grant_amount=300, monthly_limit=300,
                           split_method=models.SplitMethod.equal, approval_required=False)
    # Split by income, to show that method off too.
    groceries = _make_pot(db, ws, name="Groceries", type=models.PotType.spending,
                           budget_or_grant_amount=800, monthly_limit=800,
                           split_method=models.SplitMethod.income, approval_required=False)
    # Split by custom shares, and the one pot with approval on (over $200) — any
    # OTHER roommate can approve. The deadline is deliberately close (30 days out
    # from whenever this is seeded, not a fixed calendar date) so the deposits
    # below reliably land it behind pace regardless of what day this runs —
    # a fixed far-future date drifts out of "behind pace" range as real time
    # passes it by, which is exactly what happened to the date this replaced.
    trip = _make_pot(
        db, ws, name="Weekend Trip", type=models.PotType.savings_goal,
        target_amount=2000, deadline=today + timedelta(days=30), start_date=m2[0],
        split_method=models.SplitMethod.custom,
        custom_shares={str(maya.id): 0.3, str(josh.id): 0.3, str(sam.id): 0.2, str(lena.id): 0.2},
        approval_required=True, approval_threshold=200,
        approver_user_ids=[u.id for u in roommates],
    )

    for month in (m2, m1, m0):
        start, end = month
        days = _days_in(start, end)

        # Maya fronts rent and most of utilities every month — she's paying well
        # beyond her equal share, which is exactly what "Who owes whom" should surface.
        _txn(db, ws, rent, date_=start, merchant="Oak Street Property Mgmt", amount=3200.0,
             category="Rent", created_by=maya)
        _txn(db, ws, utilities, date_=start + timedelta(days=3), merchant="Eversource Energy",
             amount=rng.uniform(140, 180), category="Utilities", created_by=maya)
        if rng.random() < 0.3:
            _txn(db, ws, utilities, date_=start + timedelta(days=10), merchant="Comcast",
                 amount=rng.uniform(60, 90), category="Internet", created_by=josh)

        # Groceries — everyone chips in sometimes, but Maya still covers more than her share.
        for d in _random_dates(rng, start, end, max(1, round(6 * days / 30))):
            _txn(db, ws, groceries, date_=d, merchant="Stop & Shop", amount=rng.uniform(40, 100),
                 category="Groceries", created_by=maya)
        for d in _random_dates(rng, start, end, max(1, round(2 * days / 30))):
            _txn(db, ws, groceries, date_=d, merchant="Trader Joe's", amount=rng.uniform(30, 70),
                 category="Groceries", created_by=rng.choice([josh, sam, lena]))

        # Trip fund — small deposits auto-approve; a couple of bigger ones need another
        # roommate's OK. Deliberately underfunded relative to the June 2027 deadline.
        _txn(db, ws, trip, date_=start + timedelta(days=5), merchant="Transfer to trip fund",
             amount=80.0, category="Savings Transfer", created_by=rng.choice(roommates))
        if rng.random() < 0.5:
            _txn(db, ws, trip, date_=start + timedelta(days=18), merchant="Transfer to trip fund",
                 amount=250.0, category="Savings Transfer", created_by=maya)

    # One pending trip deposit over $200 — any OTHER roommate (not Maya) can approve it.
    _txn(db, ws, trip, date_=today, merchant="Transfer to trip fund", amount=300.0,
         category="Savings Transfer", created_by=maya, force_pending=True)

    # A couple of "possibly tax-relevant" expenses so the Tax Prep Pack (off by
    # default for groups, toggle-able from Members) has something real to show once
    # someone turns it on.
    _txn(db, ws, groceries, date_=today - timedelta(days=15), merchant="Yale New Haven Health",
         amount=180.0, category="Medical", created_by=lena)
    _txn(db, ws, groceries, date_=today - timedelta(days=40), merchant="Little Sprouts Daycare",
         amount=420.0, category="Childcare", created_by=sam)


# ---------------------------------------------------------------------------
# 2. Nonprofit — "Elm Street Community Food Bank"
# ---------------------------------------------------------------------------

def _seed_nonprofit(db, rng: random.Random, today: date) -> None:
    ws = _make_workspace(db, "Elm Street Community Food Bank", models.WorkspaceType.nonprofit, tax_pack_enabled=True)
    volunteer = _make_user(db, "Priya Nair", "volunteer@demo.org")
    volunteer2 = _make_user(db, "Omar Hassan", "volunteer2@demo.org")
    volunteer3 = _make_user(db, "Grace Kim", "volunteer3@demo.org")
    treasurer = _make_user(db, "Marcus Webb", "treasurer@demo.org")
    board = _make_user(db, "Dana Okafor", "board@demo.org")
    volunteers = [volunteer, volunteer2, volunteer3]

    _member(db, ws, volunteer, models.Role.volunteer)
    _member(db, ws, volunteer2, models.Role.volunteer)
    _member(db, ws, volunteer3, models.Role.volunteer)
    _member(db, ws, treasurer, models.Role.treasurer)
    _member(db, ws, board, models.Role.board_member)

    m2 = _month_bounds(2, today)
    m1 = _month_bounds(1, today)
    m0 = _month_bounds(0, today)

    # Approval on for both grants (always), and on for General Fund only over $500.
    hunger = _make_pot(
        db, ws, name="Hunger Relief Grant", type=models.PotType.restricted_grant,
        budget_or_grant_amount=25000, disallowed_categories=["Equipment", "Salaries"],
        grantor="State Hunger Relief Fund", start_date=m2[0], end_date=date(2027, 3, 31),
        approval_required=True, approver_user_ids=[treasurer.id],
    )
    youth = _make_pot(
        db, ws, name="City Youth Meals Grant", type=models.PotType.restricted_grant,
        budget_or_grant_amount=10000, allowed_categories=["Youth Meals"],
        grantor="City of New Haven", start_date=m2[0], end_date=date(2027, 6, 30),
        approval_required=True, approver_user_ids=[treasurer.id],
    )
    general = _make_pot(
        db, ws, name="General Fund", type=models.PotType.free_use, budget_or_grant_amount=12000,
        approval_required=True, approval_threshold=500, approver_user_ids=[treasurer.id],
    )

    hunger_merchants = ["Costco Wholesale", "Walmart Supercenter", "Shaw's Supermarket"]
    transport_merchants = ["Valero Gas Station", "Regional Transit Authority", "U-Haul Rental"]
    youth_merchants = ["Sysco Foodservice", "Subway Catering", "Panera Catering"]
    general_items = [
        ("Eversource Energy", "Utilities", 180, 420),
        ("Staples", "Office Supplies", 25, 150),
        ("Town Property Management", "Rent", 900, 900),
        ("Verizon Wireless", "Phone", 80, 140),
    ]

    for month in (m2, m1, m0):
        start, end = month
        days = _days_in(start, end)
        n_total = max(1, round(28 * days / 30))
        n_hunger = round(n_total * 0.45)
        n_youth = round(n_total * 0.25)
        n_general = max(1, n_total - n_hunger - n_youth)

        for d in _random_dates(rng, start, end, n_hunger):
            if rng.random() < 0.6:
                merchant, category, amt = rng.choice(hunger_merchants), "Food", rng.uniform(80, 450)
            else:
                merchant, category, amt = rng.choice(transport_merchants), "Transport", rng.uniform(40, 220)
            _txn(db, ws, hunger, date_=d, merchant=merchant, amount=amt, category=category,
                 created_by=rng.choice(volunteers))

        for d in _random_dates(rng, start, end, n_youth):
            _txn(db, ws, youth, date_=d, merchant=rng.choice(youth_merchants), amount=rng.uniform(60, 500),
                 category="Youth Meals", created_by=rng.choice(volunteers))

        for d in _random_dates(rng, start, end, n_general):
            merchant, category, lo, hi = rng.choice(general_items)
            _txn(db, ws, general, date_=d, merchant=merchant, amount=rng.uniform(lo, hi),
                 category=category, created_by=rng.choice(volunteers))

    # One mistake left PENDING on purpose — this is the exact example from the spec:
    # "this $1,100 laptop is waiting for approval and breaks the Hunger Relief Grant
    # rules." It shows up on the Approvals page AND in Needs Attention.
    _txn(db, ws, hunger, date_=today, merchant="Best Buy", amount=1100.0, category="Equipment",
         created_by=volunteer2, force_pending=True)

    # Two more mistakes, already (mistakenly) approved by the treasurer — shows the
    # rules engine catches a problem even after the fact, not just at approval time.
    mistake_date = m1[0] + timedelta(days=10)
    _txn(db, ws, hunger, date_=mistake_date, merchant="Payroll - Part-time Driver", amount=650.0,
         category="Salaries", created_by=volunteer)
    _txn(db, ws, youth, date_=mistake_date + timedelta(days=4), merchant="Staples", amount=85.0,
         category="Office Supplies", created_by=volunteer3)

    # A rejected expense, with a reason — so "whoever added it can see why" has a
    # real example.
    _txn(db, ws, general, date_=today - timedelta(days=2), merchant="Staples", amount=640.0,
         category="Office Supplies", created_by=volunteer3,
         reject_with="This was a personal purchase, not a food bank expense — please resubmit with a receipt.")

    # Another left pending so the treasurer has more than one thing to review.
    _txn(db, ws, general, date_=today, merchant="Staples", amount=64.0, category="Office Supplies",
         created_by=volunteer, force_pending=True)

    # Two donations ($250+, category "Donation") so the Tax Prep Pack's donor
    # acknowledgment-letter draft has real examples to show — negative amount, same
    # "money coming in" convention the business workspace already uses for sales.
    _txn(db, ws, general, date_=today - timedelta(days=20), merchant="Eleanor Vance", amount=-500.0,
         category="Donation", created_by=treasurer)
    _txn(db, ws, general, date_=today - timedelta(days=45), merchant="Riverside Hardware", amount=-275.0,
         category="Donation", created_by=treasurer)

    # `board` has no transactions by design — the board member role is view-only.


# ---------------------------------------------------------------------------
# 3. Business — "Corner Coffee Co." (Connecticut)
# ---------------------------------------------------------------------------

def _seed_business(db, rng: random.Random, today: date) -> None:
    ws = _make_workspace(db, "Corner Coffee Co.", models.WorkspaceType.business, tax_pack_enabled=True, state="CT")
    owner = _make_user(db, "Theo Marsh", "owner@demo.org")
    staff = _make_user(db, "Jordan Lee", "staff@demo.org")
    staff2 = _make_user(db, "Riley Brooks", "staff2@demo.org")
    bookkeeper = _make_user(db, "Alicia Fontaine", "bookkeeper@demo.org")
    staffers = [staff, staff2]

    _member(db, ws, owner, models.Role.owner)
    _member(db, ws, staff, models.Role.staff)
    _member(db, ws, staff2, models.Role.staff)
    _member(db, ws, bookkeeper, models.Role.bookkeeper)

    SALES_TAX_RATE = 0.0635  # Connecticut sales tax
    PROFIT_TAX_RATE = 0.25

    # Approval on for Payroll (always) and Operating (over $300); off for the
    # Emergency reserve and the two tax-transfer pots.
    operating = _make_pot(db, ws, name="Operating", type=models.PotType.free_use,
                           approval_required=True, approval_threshold=300, approver_user_ids=[owner.id])
    sales_tax = _make_pot(db, ws, name="Sales Tax Savings", type=models.PotType.reserve, approval_required=False)
    quarterly_tax = _make_pot(db, ws, name="Quarterly Tax Savings", type=models.PotType.reserve, approval_required=False)
    payroll = _make_pot(db, ws, name="Payroll", type=models.PotType.spending, budget_or_grant_amount=15000,
                         approval_required=True, approver_user_ids=[owner.id])
    reserve = _make_pot(db, ws, name="Emergency Reserve", type=models.PotType.reserve,
                         budget_or_grant_amount=10000, approval_required=False)

    window_start, _ = _month_bounds(2, today)
    total_sales = 0.0
    total_costs = 0.0
    this_month_start, _ = _month_bounds(0, today)
    this_month_tax_owed = 0.0

    # Weekly sales + weekly costs (Square fees scale with sales; Sysco deliveries vary).
    week_start = window_start
    while week_start <= today:
        week_end = min(week_start + timedelta(days=6), today)
        weekly_sales = rng.uniform(3200, 5100)
        total_sales += weekly_sales
        _txn(db, ws, operating, date_=week_end, merchant="Square Payout", amount=-weekly_sales,
             category="Sales", created_by=rng.choice(staffers))

        square_fee = weekly_sales * 0.026
        total_costs += square_fee
        _txn(db, ws, operating, date_=week_end, merchant="Square Fees", amount=square_fee,
             category="Processing Fees", created_by=rng.choice(staffers))

        for _ in range(rng.choice([1, 1, 2])):
            cost = rng.uniform(280, 780)
            total_costs += cost
            d = min(week_start + timedelta(days=rng.randint(0, 6)), today)
            _txn(db, ws, operating, date_=d, merchant="Sysco", amount=cost,
                 category="Supplies", created_by=rng.choice(staffers))

        tax_owed = weekly_sales * SALES_TAX_RATE
        in_current_month = week_end >= this_month_start
        tax_paid = tax_owed * (0.4 if in_current_month else 1.0)
        if in_current_month:
            this_month_tax_owed += tax_owed
        _txn(db, ws, sales_tax, date_=week_end, merchant="Tax Reserve Transfer", amount=tax_paid,
             category="Tax Reserve", created_by=rng.choice(staffers))

        week_start += timedelta(days=7)

    sales_tax.monthly_limit = round(this_month_tax_owed, 2)

    # Monthly fixed costs: rent and utilities.
    for month in (_month_bounds(2, today), _month_bounds(1, today), _month_bounds(0, today)):
        start, _ = month
        total_costs += 2500.0
        _txn(db, ws, operating, date_=start, merchant="Elm Street Realty", amount=2500.0,
             category="Rent", created_by=rng.choice(staffers))
        utilities = rng.uniform(320, 480)
        total_costs += utilities
        _txn(db, ws, operating, date_=start + timedelta(days=2), merchant="Eversource Energy",
             amount=utilities, category="Utilities", created_by=rng.choice(staffers))

    # Biweekly payroll for 3 part-time staff.
    pay_date = window_start + timedelta(days=4)
    while pay_date <= today:
        payroll_cost = 3 * 20 * 2 * 16.0  # 3 staff, ~20 hrs/week, 2 weeks, $16/hr
        total_costs += payroll_cost
        _txn(db, ws, payroll, date_=pay_date, merchant="Payroll - Part-time Staff", amount=payroll_cost,
             category="Payroll", created_by=rng.choice(staffers))
        pay_date += timedelta(days=14)

    # One quarterly profit-tax transfer.
    profit = max(total_sales - total_costs, 0.0)
    quarterly_amount = profit * PROFIT_TAX_RATE
    quarter_date = _month_bounds(1, today)[1]
    _txn(db, ws, quarterly_tax, date_=quarter_date, merchant="Tax Reserve Transfer",
         amount=quarterly_amount, category="Tax Reserve", created_by=rng.choice(staffers))

    # Emergency reserve: a modest, steady deposit each month — on pace, no issue.
    for month in (_month_bounds(2, today), _month_bounds(1, today), _month_bounds(0, today)):
        start, _ = month
        _txn(db, ws, reserve, date_=start + timedelta(days=5), merchant="Transfer to reserve",
             amount=400.0, category="Reserve Transfer", created_by=rng.choice(staffers))

    # A couple left pending for the owner to approve (Operating over $300 requires it).
    _txn(db, ws, operating, date_=today, merchant="Sysco", amount=410.0, category="Supplies",
         created_by=staff, force_pending=True)
    _txn(db, ws, payroll, date_=today, merchant="Payroll - Part-time Staff", amount=1920.0,
         category="Payroll", created_by=staff2, force_pending=True)

    # `bookkeeper` has no transactions by design — the bookkeeper role is view-only.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        if db.query(models.User).filter_by(email="maya@demo.org").first():
            return  # already seeded
        rng = random.Random(RNG_SEED)
        today = date.today()
        _seed_group(db, rng, today)
        _seed_nonprofit(db, rng, today)
        _seed_business(db, rng, today)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
