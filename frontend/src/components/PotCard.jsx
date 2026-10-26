import { useState } from 'react'
import PotApprovalEditor from './PotApprovalEditor'
import { POT_TYPE_LABELS, SPLIT_METHOD_LABELS } from '../lib/permissions'
import { getPotTheme } from '../lib/potTheme'
import { formatUSD, formatUSDate } from '../lib/format'

// Goals and reserves build UP toward a target — getting closer is good, so they
// always show a positive green fill. Spending/grant pots are used DOWN from a
// budget, so the fill turns orange past 80% and red past 100% (over budget) —
// `status` (ok/warning/over) is computed server-side by rules.pot_usage().
const BUILDS_UP = new Set(['savings_goal', 'reserve'])

const PERIOD_LABEL = {
  'this month': "this month's budget",
  lifetime: 'total budget',
  goal: 'goal',
  reserve: 'target',
}

function approvalLabel(pot) {
  if (!pot.approval_required) return 'Approval off'
  if (pot.approval_threshold) return `Approval over ${formatUSD(pot.approval_threshold)}`
  return 'Approval required'
}

export default function PotCard({ pot, workspaceId, members, canManagePots, onChanged }) {
  const [editingApproval, setEditingApproval] = useState(false)
  const buildsUp = BUILDS_UP.has(pot.type)
  const barPct = pot.period_pct == null ? 0 : Math.min(100, Math.max(0, pot.period_pct))
  const { Icon: TypeIcon, chip, solid } = getPotTheme(pot)

  // Building-up pots (goals/reserves) have no "over/warning" concept — just
  // progress toward a target — so the fill can safely use the pot's own
  // decorative accent color. Budget-style pots keep their status-driven
  // color (red/amber/slate) unchanged — that one's a real signal, not decor.
  let barColor = solid
  if (!buildsUp) {
    if (pot.status === 'over') barColor = 'bg-rose-500'
    else if (pot.status === 'warning') barColor = 'bg-amber-500'
    else barColor = 'bg-slate-400'
  }

  const displayAmount = buildsUp ? pot.current_balance : pot.period_limit != null ? pot.period_limit - pot.period_used : pot.current_balance

  return (
    <div className="w-full rounded-xl border border-slate-200 bg-white p-4 card-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`shrink-0 inline-flex items-center justify-center w-9 h-9 rounded-xl ${chip}`}>
            {TypeIcon && <TypeIcon size={18} strokeWidth={2} />}
          </span>
          <h3 className="font-semibold text-slate-900 truncate">{pot.name}</h3>
        </div>
        <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${chip}`}>
          {POT_TYPE_LABELS[pot.type]}
        </span>
      </div>

      <p className="text-3xl font-bold text-slate-900 tabular-nums tracking-tight">{formatUSD(displayAmount)}</p>
      {pot.period_limit != null && (
        <>
          <p className="text-xs text-slate-500 mb-1.5 mt-0.5">
            {buildsUp
              ? `saved of ${formatUSD(pot.period_limit)} ${PERIOD_LABEL[pot.period]}`
              : `remaining of ${formatUSD(pot.period_limit)} ${PERIOD_LABEL[pot.period]}`}
            {!buildsUp && pot.status === 'over' && <span className="text-rose-600 font-semibold"> — over budget</span>}
          </p>
          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${barPct}%` }} />
          </div>
        </>
      )}

      <dl className="mt-3 text-xs text-slate-500 space-y-0.5">
        {pot.monthly_limit != null && pot.type !== 'reserve' && (
          <div>Monthly limit: {formatUSD(pot.monthly_limit)}</div>
        )}
        {pot.deadline && <div>Deadline: {formatUSDate(pot.deadline)}</div>}
        {pot.grantor && <div>Grantor: {pot.grantor}</div>}
        {(pot.start_date || pot.end_date) && (
          <div>
            {pot.start_date ? formatUSDate(pot.start_date) : '—'} to{' '}
            {pot.end_date ? formatUSDate(pot.end_date) : '—'}
          </div>
        )}
        {pot.split_method && <div>Split: {SPLIT_METHOD_LABELS[pot.split_method]}</div>}
      </dl>

      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between">
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            pot.approval_required ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'
          }`}
        >
          {approvalLabel(pot)}
        </span>
        {canManagePots && (
          <button
            onClick={() => setEditingApproval((s) => !s)}
            className="text-xs text-emerald-700 hover:underline"
          >
            {editingApproval ? 'Close' : 'Manage'}
          </button>
        )}
      </div>

      {editingApproval && (
        <PotApprovalEditor
          workspaceId={workspaceId}
          pot={pot}
          members={members}
          onSaved={() => {
            setEditingApproval(false)
            onChanged()
          }}
          onCancel={() => setEditingApproval(false)}
        />
      )}
    </div>
  )
}
