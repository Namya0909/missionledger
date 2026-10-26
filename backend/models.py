"""SQLAlchemy ORM models for MissionLedger.

Covers: workspaces, users, memberships (role per workspace), pots (with split and
approval settings), transactions, an audit log, AI token/cost usage, and tester
feedback.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkspaceType(str, enum.Enum):
    group = "group"  # any 2-10 people sharing money: a couple, family, roommates, trip
    nonprofit = "nonprofit"
    business = "business"


class WorkspaceStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class Role(str, enum.Enum):
    # group
    member = "member"
    admin = "admin"
    # nonprofit
    volunteer = "volunteer"
    treasurer = "treasurer"
    board_member = "board_member"
    # business
    owner = "owner"
    staff = "staff"
    bookkeeper = "bookkeeper"


# Which roles are valid for which workspace type. Enforced in the API layer
# (routers/memberships.py) so we can return a clear, friendly error message.
ROLES_BY_WORKSPACE_TYPE: dict[WorkspaceType, list[Role]] = {
    WorkspaceType.group: [Role.member, Role.admin],
    WorkspaceType.nonprofit: [Role.volunteer, Role.treasurer, Role.board_member],
    WorkspaceType.business: [Role.owner, Role.staff, Role.bookkeeper],
}

GROUP_MIN_MEMBERS = 2
GROUP_MAX_MEMBERS = 10


class PotType(str, enum.Enum):
    spending = "spending"
    savings_goal = "savings_goal"
    restricted_grant = "restricted_grant"
    reserve = "reserve"
    free_use = "free_use"


# Pot types that build UP toward a target (savings goal, reserve cushion) — a
# transaction on one of these is a deposit, starting at $0. Every other type
# tracks remaining budget, depleting DOWN from the full budget/grant amount.
DEPOSIT_POT_TYPES = {PotType.savings_goal, PotType.reserve}


class SplitMethod(str, enum.Enum):
    equal = "equal"      # every member owes 1/N
    income = "income"    # owed share proportional to each member's recorded income
    custom = "custom"    # owed share set explicitly per member (e.g. 40/30/30)


class TransactionStatus(str, enum.Enum):
    pending = "pending"       # "waiting"
    approved = "approved"
    rejected = "rejected"


class TransactionSource(str, enum.Enum):
    typed = "typed"
    uploaded_file = "uploaded_file"
    receipt_photo = "receipt_photo"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[WorkspaceType] = mapped_column(Enum(WorkspaceType), nullable=False)
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus), nullable=False, default=WorkspaceStatus.active
    )
    # Optional, never required: a 2-person group can confirm they're a couple so the
    # UI can use warmer framing. None = not asked/answered yet.
    is_couple: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Opt-in, off by default — gates the Tax Prep Pack tab (see tax_prep.py). Toggled
    # at signup, at AI setup time, or anytime after from the Members tab.
    tax_pack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Two-letter US state code, business workspaces only — used to look up a real
    # sales-tax rate for the Tax Prep Pack's worksheet (tax_config.STATE_SALES_TAX_RATES)
    # instead of guessing. None for group/nonprofit workspaces, or a business that
    # hasn't set one yet (falls back to tax_config.DEFAULT_SALES_TAX_RATE, flagged as
    # an estimate).
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    pots: Mapped[list["Pot"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Login lockout (persistent — a rolling in-memory rate limit alone wouldn't
    # survive a restart, and a brute-force attempt shouldn't get a fresh start
    # just because the server restarted).
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class SecurityAnswer(Base):
    """One of a user's 3 chosen security questions + its hashed answer (bcrypt, same
    as the password). Deliberately one-row-per-answer rather than fixed columns,
    since "pick 3 of a pool" is a natural one-row-per-choice shape — see
    security_questions.py for the pool itself."""

    __tablename__ = "security_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_key: Mapped[str] = mapped_column(String(50), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Membership(Base):
    """Links a user to a workspace with a role."""

    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    # Used only for a group's "split by income" pots.
    monthly_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")


class Pot(Base):
    __tablename__ = "pots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[PotType] = mapped_column(Enum(PotType), nullable=False)

    budget_or_grant_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Savings-goal specific
    target_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Spending-rule fields
    monthly_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    disallowed_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Restricted-grant specific
    grantor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [{"date": "2026-03-31", "description": "Quarterly progress report"}, ...] —
    # extracted by the Intake helper from a grant agreement PDF, if any.
    report_deadlines: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # How this pot's cost is divided among a group's members (settleup.py reads
    # this). None means the pot isn't split/shared (e.g. most nonprofit/business pots).
    split_method: Mapped[SplitMethod | None] = mapped_column(Enum(SplitMethod), nullable=True)
    # Only for split_method == custom: {user_id (str): fraction}, must sum to 1.0.
    custom_shares: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Approval switch. When off, every transaction on this pot auto-approves. When
    # on, a transaction needs a decision from someone in approver_user_ids — unless
    # approval_threshold is set, in which case only amounts OVER it need approval.
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    approver_user_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workspace: Mapped["Workspace"] = relationship(back_populates="pots")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="pot")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    pot_id: Mapped[int] = mapped_column(ForeignKey("pots.id"), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    merchant: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), nullable=False, default=TransactionStatus.pending
    )
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource), nullable=False, default=TransactionSource.typed
    )
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workspace: Mapped["Workspace"] = relationship(back_populates="transactions")
    pot: Mapped["Pot"] = relationship(back_populates="transactions")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])


class InviteLink(Base):
    """A shareable link for one role — anyone with it can join that workspace with
    that role, without an admin needing their email up front. Reusable until
    deactivated, not single-use, since e.g. a "volunteer" link may be shared with
    several people over time."""

    __tablename__ = "invite_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)  # human-friendly, e.g. "Volunteers"
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workspace: Mapped["Workspace"] = relationship()


class Settlement(Base):
    """A real payment one group member made to another to settle a balance —
    recorded by hand, not inferred. settleup.py nets these against the computed
    balances so they don't just recompute from the dawn of time forever."""

    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    from_user: Mapped["User"] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship(foreign_keys=[to_user_id])


class RecurringCharge(Base):
    """A template for a fixed monthly bill (rent, a subscription) — generates a real
    Transaction once per month automatically, going through the same approval rules
    as if someone had typed it in that day."""

    __tablename__ = "recurring_charges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    pot_id: Mapped[int] = mapped_column(ForeignKey("pots.id"), nullable=False)
    merchant: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-28, kept safe for Feb
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_generated_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_generated_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pot: Mapped["Pot"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])


class AuditLogEntry(Base):
    """History log of everything people do."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SecurityLogEntry(Base):
    """Every time a defense actually blocks, redacts, throttles, or locks
    something — separate from the audit log, which records normal user actions."""

    __tablename__ = "security_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    defense: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIUsageLog(Base):
    """How many AI tokens each request uses and what it costs."""

    __tablename__ = "ai_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Ties multiple AI calls back to the one user-facing request that caused them
    # (e.g. one chat message -> Gatekeeper + Orchestrator + Analyst all share one
    # id) so "average cost per request" is a real grouped average, not a guess.
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_with: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
