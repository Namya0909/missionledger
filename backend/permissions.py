"""Who can do what — checked on the server, never trusted from the client.

Every capability check here takes the membership row that proves who the
caller is (looked up from their JWT, never from a client-supplied user id)
and the workspace's type, and returns a plain bool. Routers call these
instead of hard-coding role lists so the rule lives in exactly one place.

Approval is no longer tied to a role (e.g. "treasurer approves") — it's a
per-pot setting (see models.Pot.approval_required/approval_threshold/
approver_user_ids), managed by whoever has manage_pots. See needs_approval()
and can_decide() below.
"""

import enum

from sqlalchemy.orm import Session

from models import Membership, Pot, Role, Transaction, TransactionStatus, WorkspaceType


class Capability(str, enum.Enum):
    create_transaction = "create_transaction"  # "add an expense"
    manage_pots = "manage_pots"                # create/edit pots, incl. approval settings
    manage_members = "manage_members"          # invite members
    view_security_log = "view_security_log"    # see this workspace's security events


# Roles not listed for a given workspace type have none of these capabilities —
# e.g. a nonprofit board_member or business bookkeeper can only look.
#
# view_security_log is granted to the same role that already has manage_pots in
# each workspace type — reusing that existing trust tier rather than inventing a
# new "admin" concept (MissionLedger has no app-wide superuser; see security_log).
ROLE_CAPABILITIES: dict[WorkspaceType, dict[Role, set[Capability]]] = {
    WorkspaceType.group: {
        # Anyone in the group can add expenses; one or two admins run the group.
        Role.member: {Capability.create_transaction},
        Role.admin: {
            Capability.create_transaction,
            Capability.manage_pots,
            Capability.manage_members,
            Capability.view_security_log,
        },
    },
    WorkspaceType.nonprofit: {
        Role.volunteer: {Capability.create_transaction},
        Role.treasurer: {Capability.manage_pots, Capability.manage_members, Capability.view_security_log},
        Role.board_member: set(),  # "the board can only look"
    },
    WorkspaceType.business: {
        Role.staff: {Capability.create_transaction},
        Role.owner: {Capability.manage_pots, Capability.manage_members, Capability.view_security_log},
        Role.bookkeeper: set(),  # "bookkeeper can only look"
    },
}


def has_capability(workspace_type: WorkspaceType, role: Role, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES.get(workspace_type, {}).get(role, set())


def is_privileged_anywhere(memberships: list[Membership]) -> bool:
    """For app-wide pages that don't belong to any one workspace (Costs, feature
    flags) — true if the user has view_security_log in at least one of their
    workspaces. No new global-admin concept, just reusing the existing per-
    workspace trust tier across all of a user's memberships."""
    return any(
        has_capability(m.workspace.type, m.role, Capability.view_security_log) for m in memberships
    )


def is_sole_privileged_member(membership: Membership, db: Session) -> bool:
    """True if `membership` is the only one in its workspace holding
    manage_members — removing or demoting them would strand the workspace with
    nobody able to manage pots, invite/remove members, or view its security log."""
    if not can_manage_members(membership, membership.workspace.type):
        return False
    peers = db.query(Membership).filter_by(workspace_id=membership.workspace_id).all()
    return not any(
        m.id != membership.id and can_manage_members(m, membership.workspace.type) for m in peers
    )


def can_create_transaction(membership: Membership, workspace_type: WorkspaceType) -> bool:
    return has_capability(workspace_type, membership.role, Capability.create_transaction)


def can_manage_pots(membership: Membership, workspace_type: WorkspaceType) -> bool:
    return has_capability(workspace_type, membership.role, Capability.manage_pots)


def can_manage_members(membership: Membership, workspace_type: WorkspaceType) -> bool:
    return has_capability(workspace_type, membership.role, Capability.manage_members)


def can_edit_or_delete_transaction(
    transaction: Transaction, membership: Membership, workspace_type: WorkspaceType, user_id: int
) -> bool:
    """You can always fix or remove your own expense (typo, duplicate, wrong amount) —
    whatever its status, since the one who entered it is best placed to correct it.
    Admins/treasurers/owners (manage_pots) can do the same for anyone's, to correct
    or clean up records they're accountable for workspace-wide."""
    if transaction.created_by_user_id == user_id:
        return True
    return can_manage_pots(membership, workspace_type)


# ---------------------------------------------------------------------------
# Per-pot approval
# ---------------------------------------------------------------------------

def needs_approval(pot: Pot, amount: float) -> bool:
    """Whether a new transaction on this pot must wait for a decision."""
    if not pot.approval_required:
        return False
    if pot.approval_threshold is not None:
        return abs(amount) > pot.approval_threshold
    return True


def eligible_approvers(pot: Pot) -> set[int]:
    return set(pot.approver_user_ids or [])


def can_decide(pot: Pot, transaction: Transaction, user_id: int) -> tuple[bool, str]:
    """Returns (allowed, reason_if_not). Nobody may approve their own expense, and
    only someone on the pot's approver list may decide at all."""
    if transaction.created_by_user_id == user_id:
        return False, "You cannot approve or reject your own expense."
    approvers = eligible_approvers(pot)
    if not approvers:
        return False, "This pot has no approvers chosen yet."
    if user_id not in approvers:
        return False, "You are not an approver for this pot."
    return True, ""


def waiting_reason(pot: Pot, transaction: Transaction) -> str | None:
    """Explains a pending transaction that's stuck waiting — e.g. its only eligible
    approver is also the person who added it. None if nothing is unusual."""
    if transaction.status != TransactionStatus.pending:
        return None
    approvers = eligible_approvers(pot)
    if not approvers:
        return "Waiting — this pot requires approval but has no approvers chosen yet."
    if approvers - {transaction.created_by_user_id} == set():
        return "Waiting for another approver — the only approver for this pot is also who added this expense."
    return None
