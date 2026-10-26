"""Pydantic request/response schemas."""

from datetime import date, datetime
# `date: date | None = None` would bind `date` to its own default before the
# annotation evaluates (a real Python gotcha) — this alias is for fields named "date".
from datetime import date as _date

from pydantic import BaseModel, EmailStr, Field

from models import (
    PotType,
    Role,
    SplitMethod,
    TransactionSource,
    TransactionStatus,
    WorkspaceStatus,
    WorkspaceType,
)


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------

class SecurityAnswerIn(BaseModel):
    question_key: str
    answer: str


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    security_answers: list[SecurityAnswerIn] = Field(min_length=3, max_length=3)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    is_feedback_admin: bool = False

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SecurityQuestionOut(BaseModel):
    key: str
    question: str
    options: list[str]


class LoginStep1Response(BaseModel):
    status: str = "needs_security_answers"
    login_ticket: str
    questions: list[SecurityQuestionOut]


class SecurityAnswerVerify(BaseModel):
    login_ticket: str
    answers: list[SecurityAnswerIn] = Field(min_length=3, max_length=3)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Workspaces & Memberships
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    name: str
    type: WorkspaceType
    tax_pack_enabled: bool = False
    state: str | None = None  # two-letter US state code; business workspaces only


class WorkspaceOut(BaseModel):
    id: int
    name: str
    type: WorkspaceType
    status: WorkspaceStatus
    is_couple: bool | None
    tax_pack_enabled: bool
    state: str | None
    member_count: int
    role: Role  # the CALLING user's own role in this workspace — lets the frontend show/hide admin-only nav without a round trip
    created_at: datetime

    model_config = {"from_attributes": True}


class CoupleUpdate(BaseModel):
    is_couple: bool


class TaxPackEnabledUpdate(BaseModel):
    enabled: bool


class MembershipCreate(BaseModel):
    email: EmailStr  # invite by email; user must already have an account
    role: Role
    monthly_income: float | None = None


class IncomeUpdate(BaseModel):
    monthly_income: float | None


class RoleUpdate(BaseModel):
    role: Role


class MembershipOut(BaseModel):
    id: int
    role: Role
    monthly_income: float | None
    user: UserOut
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pots
# ---------------------------------------------------------------------------

class PotCreate(BaseModel):
    name: str
    type: PotType
    budget_or_grant_amount: float | None = None
    target_amount: float | None = None
    deadline: date | None = None
    monthly_limit: float | None = None
    allowed_categories: list[str] | None = None
    disallowed_categories: list[str] | None = None
    grantor: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    split_method: SplitMethod | None = None
    custom_shares: dict[str, float] | None = None
    approval_required: bool = True
    approval_threshold: float | None = None
    approver_user_ids: list[int] | None = None
    report_deadlines: list[dict] | None = None


class PotApprovalUpdate(BaseModel):
    approval_required: bool
    approval_threshold: float | None = None
    approver_user_ids: list[int] = Field(default_factory=list)


class PotOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    type: PotType
    budget_or_grant_amount: float | None
    current_balance: float
    target_amount: float | None
    deadline: date | None
    monthly_limit: float | None
    allowed_categories: list[str] | None
    disallowed_categories: list[str] | None
    grantor: str | None
    start_date: date | None
    end_date: date | None
    split_method: SplitMethod | None
    custom_shares: dict | None
    approval_required: bool
    approval_threshold: float | None
    approver_user_ids: list[int] | None
    report_deadlines: list[dict] | None
    created_at: datetime

    # Computed by rules.pot_usage() — "how used up this pot is," measured the way
    # that's meaningful for its type (see rules.py). The frontend displays these
    # instead of raw current_balance, which for a recurring monthly budget is a
    # lifetime total across every month ever, not "how much is left this month."
    period: str
    period_used: float
    period_limit: float | None
    period_pct: float | None
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    pot_id: int
    date: date
    merchant: str
    description: str | None = None
    amount: float
    category: str | None = None
    source: TransactionSource = TransactionSource.typed


class TransactionUpdate(BaseModel):
    pot_id: int
    date: date
    merchant: str
    description: str | None = None
    amount: float
    category: str | None = None


class TransactionDecision(BaseModel):
    approve: bool
    reason: str | None = None  # required in practice when rejecting; see routers/approvals.py


class TransactionOut(BaseModel):
    id: int
    workspace_id: int
    pot_id: int
    pot_name: str
    date: date
    merchant: str
    description: str | None
    amount: float
    category: str | None
    status: TransactionStatus
    source: TransactionSource
    warnings: list[str] | None
    rejection_reason: str | None
    waiting_reason: str | None
    can_i_decide: bool
    decide_blocked_reason: str | None  # why can_i_decide is false for the caller, when pending
    can_i_edit: bool  # true for the person who created it, or anyone who manages pots
    has_receipt: bool
    created_by_user_id: int
    created_by_name: str
    approved_by_user_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Settle up (groups)
# ---------------------------------------------------------------------------

class BalanceOut(BaseModel):
    user_id: int
    name: str
    amount: float  # positive = owed money by the group, negative = owes the group


class TransferOut(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: float


class SettleUpOut(BaseModel):
    balances: list[BalanceOut]
    transfers: list[TransferOut]


class SettlementCreate(BaseModel):
    to_user_id: int
    amount: float = Field(gt=0)
    note: str | None = None


class SettlementOut(BaseModel):
    id: int
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: float
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Recurring charges
# ---------------------------------------------------------------------------

class RecurringChargeCreate(BaseModel):
    pot_id: int
    merchant: str
    amount: float
    category: str | None = None
    day_of_month: int = Field(ge=1, le=28)


class RecurringChargeOut(BaseModel):
    id: int
    pot_id: int
    pot_name: str
    merchant: str
    amount: float
    category: str | None
    day_of_month: int
    active: bool
    created_by_name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: int
    action: str
    details: dict | None
    user_name: str | None
    created_at: datetime


class SecurityLogOut(BaseModel):
    id: int
    defense: str
    action: str
    detail: str
    user_name: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Feedback & AI usage
# ---------------------------------------------------------------------------

class FeedbackCreate(BaseModel):
    workspace_id: int | None = None
    message: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    minutes_before: int | None = Field(default=None, ge=0)
    minutes_with: int | None = Field(default=None, ge=0)
    reviewer_role: str | None = None
    structured_answers: dict | None = None


class FeedbackOut(BaseModel):
    id: int
    user_id: int | None
    workspace_id: int | None
    message: str | None
    rating: int | None
    minutes_before: int | None
    minutes_with: int | None
    reviewer_role: str | None
    structured_answers: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackSummaryOut(BaseModel):
    response_count: int
    avg_rating: float | None
    avg_minutes_before: float | None
    avg_minutes_with: float | None
    avg_minutes_saved: float | None
    by_role: dict[str, int] = Field(default_factory=dict)


class AttentionItemOut(BaseModel):
    pot_id: int
    pot_name: str
    kind: str
    detail: str
    transaction_id: int | None
    explanation: str
    suggested_fix: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class TraceStepOut(BaseModel):
    helper: str
    tool: str | None = None
    args: dict | None = None
    result: str
    input_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class ChatResponse(BaseModel):
    reply: str
    blocked: bool
    trace: list[TraceStepOut] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_cached_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


class AIUsageOut(BaseModel):
    id: int
    request_id: str
    purpose: str
    model_name: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Setup Agent (conversational onboarding)
# ---------------------------------------------------------------------------

class SetupHistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SetupMessage(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[SetupHistoryItem] = Field(default_factory=list)


class PlanPotOut(BaseModel):
    name: str
    type: PotType
    budget_or_grant_amount: float | None = None
    target_amount: float | None = None
    deadline: date | None = None  # a goal's target date, or a grant's end date
    monthly_limit: float | None = None
    allowed_categories: list[str] = Field(default_factory=list)
    split_method: SplitMethod | None = None
    approval_required: bool = False
    approval_reason: str | None = None  # why suggested, shown next to the toggle


class InviteSuggestionOut(BaseModel):
    role: Role
    label: str  # human-friendly, e.g. "Volunteers"
    note: str | None = None


class SavingsAnalysisOut(BaseModel):
    goal_amount: float
    months_left: float
    required_monthly: float
    monthly_capacity: float | None
    feasible: bool
    shortfall_per_month: float | None
    options: list[str]


class SetupPlanOut(BaseModel):
    workspace_type: WorkspaceType
    suggested_name: str
    summary: str
    pots: list[PlanPotOut]
    invites: list[InviteSuggestionOut]
    savings_analysis: SavingsAnalysisOut | None = None
    state: str | None = None  # two-letter US state code; business plans only


class SetupResponse(BaseModel):
    reply: str
    declined: bool
    done: bool  # true once a plan is ready (or declined) — nothing is saved yet
    question_number: int  # 0 before any question, 1-4 while asking
    plan: SetupPlanOut | None = None
    error: str | None = None  # a friendly message if structured plan generation failed twice


class CreateFromPlanRequest(BaseModel):
    workspace_type: WorkspaceType
    suggested_name: str
    pots: list[PlanPotOut]
    invites: list[InviteSuggestionOut]
    tax_pack_enabled: bool = False
    state: str | None = None


class InviteLinkOut(BaseModel):
    role: Role
    label: str
    token: str
    url: str


class CreateFromPlanResponse(BaseModel):
    workspace_id: int
    invite_links: list[InviteLinkOut]


class InvitePreviewOut(BaseModel):
    workspace_name: str
    workspace_type: WorkspaceType
    role: Role
    label: str


class InviteAcceptResponse(BaseModel):
    workspace_id: int
    workspace_name: str


# ---------------------------------------------------------------------------
# Intake (statement CSV / receipt photo / grant PDF)
# ---------------------------------------------------------------------------

class IntakeStatementRowOut(BaseModel):
    date: date
    merchant: str
    amount: float
    suggested_pot: str
    suggested_category: str


class IntakeStatementResponse(BaseModel):
    rows: list[IntakeStatementRowOut]


class IntakeReceiptResponse(BaseModel):
    vision_available: bool
    message: str | None = None  # set when vision_available is False
    store: str | None = None
    date: _date | None = None
    amount: float | None = None
    items: list[str] = Field(default_factory=list)
    suggested_category: str | None = None
    suggested_pot: str | None = None


class ReportDeadlineOut(BaseModel):
    date: date
    description: str


class IntakeGrantResponse(BaseModel):
    grant_name: str
    grantor: str | None = None
    amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    allowed_categories: list[str] = Field(default_factory=list)
    disallowed_categories: list[str] = Field(default_factory=list)
    report_deadlines: list[ReportDeadlineOut] = Field(default_factory=list)


class ConfirmIntakeTransactionRow(BaseModel):
    date: date
    merchant: str
    amount: float
    pot_name: str
    category: str
    description: str | None = None
    source: TransactionSource = TransactionSource.uploaded_file


class ConfirmIntakeTransactionsRequest(BaseModel):
    rows: list[ConfirmIntakeTransactionRow]


class ConfirmIntakeGrantRequest(BaseModel):
    pot_name: str
    grantor: str | None = None
    amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    allowed_categories: list[str] = Field(default_factory=list)
    disallowed_categories: list[str] = Field(default_factory=list)
    report_deadlines: list[ReportDeadlineOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Costs page (app-wide; not scoped to one workspace)
# ---------------------------------------------------------------------------

class CostsByGroupOut(BaseModel):
    calls: int
    cost_usd: float
    tokens: int


class WorkspaceTypeCostsOut(CostsByGroupOut):
    workspace_type: str


class PurposeCostsOut(CostsByGroupOut):
    purpose: str


class CostsSummaryOut(BaseModel):
    total_requests: int
    total_calls: int
    total_input_tokens: int
    total_cached_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    avg_cost_per_request: float
    cache_hit_rate_pct: float
    this_month_cost_usd: float
    this_month_active_users: int
    cost_per_user_this_month: float
    projections: dict[int, float]
    by_workspace_type: list[WorkspaceTypeCostsOut]
    by_purpose: list[PurposeCostsOut]
    pricing_is_placeholder: bool
    model_name: str


class DailyTokensOut(BaseModel):
    date: str
    purpose: str
    tokens: int


class FeatureFlagOut(BaseModel):
    name: str
    enabled: bool
    description: str


class FeatureFlagUpdate(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Tax Prep Pack (organizes paperwork for tax time — never files, never advises)
# ---------------------------------------------------------------------------

class TaxLineItemOut(BaseModel):
    date: date
    merchant: str
    amount: float
    has_receipt: bool = False


class GroupTaxBucketOut(BaseModel):
    label: str
    total: float
    items: list[TaxLineItemOut]


class GroupTaxSummaryOut(BaseModel):
    year: int
    buckets: list[GroupTaxBucketOut]
    grand_total: float
    narrative: list[str] = Field(default_factory=list)


class DonorOut(BaseModel):
    donor_name: str
    amount: float
    date: date


class NonprofitTaxSummaryOut(BaseModel):
    year: int
    gross_receipts: float
    total_spending: float
    bucket_totals: dict[str, float]
    total_assets: float
    filing_recommendation: str  # "990-N" | "990-EZ" | "990"
    filing_reason: str
    irs_990_info_url: str
    donors: list[DonorOut]
    narrative: str = ""
    donor_letters: list[str] = Field(default_factory=list)


class ContractorOut(BaseModel):
    merchant: str
    total_paid: float


class BusinessTaxSummaryOut(BaseModel):
    year: int
    taxable_sales: float
    sales_tax_rate: float
    rate_is_estimate: bool
    tax_owed: float
    already_saved: float
    next_estimated_due_date: date
    contractors: list[ContractorOut]
    narrative: str = ""
