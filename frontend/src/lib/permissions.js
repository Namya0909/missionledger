// Mirrors backend/permissions.py — for UI only (show/hide buttons). The server
// enforces every one of these checks again independently; nothing here is trusted.
// Note: approving/rejecting a transaction is NOT role-based anymore — it depends on
// each pot's own approver list (see the transaction's `can_i_decide` field, which
// the server computes, rather than deriving it here).
const ROLE_CAPABILITIES = {
  group: {
    member: ['create_transaction'],
    admin: ['create_transaction', 'manage_pots', 'manage_members', 'view_security_log'],
  },
  nonprofit: {
    volunteer: ['create_transaction'],
    treasurer: ['manage_pots', 'manage_members', 'view_security_log'],
    board_member: [],
  },
  business: {
    staff: ['create_transaction'],
    owner: ['manage_pots', 'manage_members', 'view_security_log'],
    bookkeeper: [],
  },
}

export function hasCapability(workspaceType, role, capability) {
  return (ROLE_CAPABILITIES[workspaceType]?.[role] || []).includes(capability)
}

// Which roles are valid to assign on a given workspace type — e.g. for a role
// picker when adding/editing a member. Mirrors backend/models.py's
// ROLES_BY_WORKSPACE_TYPE (the server re-validates this regardless).
export function rolesForWorkspaceType(workspaceType) {
  return Object.keys(ROLE_CAPABILITIES[workspaceType] || {})
}

// Mirrors backend/permissions.py's is_privileged_anywhere — true if the user is
// admin/treasurer/owner in at least one of their workspaces. Used to hide nav
// links (Costs, Feedback) that the server would otherwise just deny with a 403.
export function isPrivilegedAnywhere(workspaces) {
  return workspaces.some((ws) => hasCapability(ws.type, ws.role, 'view_security_log'))
}

export const WORKSPACE_TYPE_LABELS = {
  group: 'Friends & Family',
  nonprofit: 'Nonprofit',
  business: 'Small Business',
}

export const WORKSPACE_TYPE_BLURBS = {
  group: 'Split rent, groceries, and trip costs with roommates, family, or a partner — track who owes whom.',
  nonprofit: 'Track grants and spending rules, catch mistakes automatically, and get board-ready reports.',
  business: 'Watch sales, payroll, and runway, and set aside the right amount for taxes as you go.',
}

export const ROLE_LABELS = {
  member: 'Member',
  admin: 'Admin',
  volunteer: 'Volunteer',
  treasurer: 'Treasurer',
  board_member: 'Board Member',
  owner: 'Owner',
  staff: 'Staff',
  bookkeeper: 'Bookkeeper',
}

export const POT_TYPE_LABELS = {
  spending: 'Spending',
  savings_goal: 'Goal',
  restricted_grant: 'Grant',
  reserve: 'Reserve',
  free_use: 'Free to Use',
}

export const SPLIT_METHOD_LABELS = {
  equal: 'Equally',
  income: 'By income',
  custom: 'Custom shares',
}
