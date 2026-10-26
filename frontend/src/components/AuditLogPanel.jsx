import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSDate } from '../lib/format'
import EmptyState from './EmptyState'

const ACTION_LABELS = {
  'workspace.created': 'Workspace created',
  'member.added': 'Member added',
  'member.removed': 'Member removed',
  'member.role_changed': 'Member role changed',
  'pot.created': 'Pot created',
  'pot.approval_settings_changed': 'Approval settings changed',
  'transaction.created': 'Expense added',
  'transaction.decided': 'Expense decided',
  'transaction.decision_blocked': 'Approval attempt blocked',
  'transaction.receipt_uploaded': 'Receipt uploaded',
  'transaction.updated': 'Expense edited',
  'transaction.deleted': 'Expense deleted',
  'settlement.recorded': 'Payment recorded',
  'recurring.created': 'Recurring charge added',
  'recurring.deactivated': 'Recurring charge removed',
}

function describe(entry) {
  const d = entry.details || {}
  switch (entry.action) {
    case 'transaction.created':
      return `added a $${d.amount?.toFixed?.(2) ?? d.amount} expense${d.required_approval ? ' (needs approval)' : ''}`
    case 'transaction.decided':
      return d.approved ? 'approved an expense' : `rejected an expense${d.reason ? `: "${d.reason}"` : ''}`
    case 'transaction.decision_blocked':
      return `tried to ${d.attempted_approve ? 'approve' : 'reject'} an expense and was blocked: "${d.reason}"`
    case 'transaction.updated': {
      const changed = []
      if (d.old?.amount !== d.new?.amount) changed.push(`amount $${d.old?.amount} → $${d.new?.amount}`)
      if (d.old?.merchant !== d.new?.merchant) changed.push(`merchant "${d.old?.merchant}" → "${d.new?.merchant}"`)
      if (d.old?.pot_name !== d.new?.pot_name) changed.push(`pot "${d.old?.pot_name}" → "${d.new?.pot_name}"`)
      return `edited an expense${changed.length ? ` (${changed.join(', ')})` : ''}`
    }
    case 'transaction.deleted':
      return `deleted a $${d.amount} expense at "${d.merchant}"${d.pot_name ? ` from ${d.pot_name}` : ''}`
    case 'pot.approval_settings_changed':
      return `changed approval settings for "${d.pot_name}"`
    case 'member.added':
      return `added ${d.added_user_email} as ${d.role}`
    case 'member.removed':
      return `removed ${d.removed_user_email} (was ${d.role})`
    case 'member.role_changed':
      return `changed ${d.user_email}'s role from ${d.old_role} to ${d.new_role}`
    case 'pot.created':
      return `created the "${d.name}" pot`
    case 'settlement.recorded':
      return `recorded a $${d.amount} payment`
    case 'recurring.created':
      return `set up a recurring $${d.amount} charge for "${d.merchant}"`
    case 'recurring.deactivated':
      return `removed the recurring charge for "${d.merchant}"`
    default:
      return JSON.stringify(d)
  }
}

export default function AuditLogPanel({ workspaceId }) {
  const [entries, setEntries] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listAuditLog(workspaceId).then(setEntries).catch((err) => setError(err.message))
  }, [workspaceId])

  if (error) return <p className="text-sm text-rose-600">{error}</p>
  if (!entries) return <p className="text-sm text-slate-500">Loading…</p>
  if (entries.length === 0) {
    return <EmptyState icon={FileText} message="Nothing logged yet — actions taken in this workspace will show up here." />
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow divide-y divide-slate-100">
      {entries.map((e) => (
        <div key={e.id} className="px-4 py-2.5 text-sm">
          <span className="font-medium text-slate-900">{e.user_name || 'System'}</span>{' '}
          <span className="text-slate-600">
            {ACTION_LABELS[e.action] ? describe(e) : e.action}
          </span>
          <span className="text-xs text-slate-400 block">{formatUSDate(e.created_at)}</span>
        </div>
      ))}
    </div>
  )
}
