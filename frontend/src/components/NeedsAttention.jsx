import useRotatingMessages from '../lib/useRotatingMessages'

const CHECKING_MESSAGES = ['Checking for problems…', 'Comparing against your budgets…', 'Checking grant rules…']

const KIND_LABEL = {
  over_budget: 'Over budget',
  disallowed_category: 'Wrong category',
  outside_grant_window: 'Outside grant window',
  goal_behind_pace: 'Falling behind',
  reserve_shortfall: 'Reserve short',
  payroll_not_covered: 'Payroll not covered',
  report_deadline_approaching: 'Report due soon',
}

export default function NeedsAttention({ items, loading }) {
  const checkingMessage = useRotatingMessages(CHECKING_MESSAGES, loading)
  if (loading) {
    return <p className="text-sm text-slate-500">{checkingMessage}</p>
  }
  if (items.length === 0) {
    return (
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-800">
        Nothing needs attention right now.
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {items.map((item, i) => (
        <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
              {KIND_LABEL[item.kind] || item.kind}
            </span>
            <span className="text-xs text-slate-500">{item.pot_name}</span>
          </div>
          <p className="text-sm text-slate-800">{item.explanation}</p>
          <p className="text-sm text-slate-600 mt-1">
            <span className="font-medium">Suggested fix:</span> {item.suggested_fix}
          </p>
        </div>
      ))}
    </div>
  )
}
