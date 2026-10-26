import { formatUSD } from '../lib/format'

export default function SetupSavingsCard({ analysis }) {
  if (!analysis) return null
  const months = analysis.months_left.toFixed(1)

  return (
    <div
      className={`rounded-xl border p-4 ${
        analysis.feasible ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-slate-900">Savings math</h3>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            analysis.feasible ? 'bg-emerald-200 text-emerald-800' : 'bg-amber-200 text-amber-900'
          }`}
        >
          {analysis.feasible ? 'On track' : 'This is tight'}
        </span>
      </div>
      <p className="text-sm text-slate-700">
        To reach {formatUSD(analysis.goal_amount)} in about {months} months, you'd need to save{' '}
        <span className="font-semibold">{formatUSD(analysis.required_monthly)}</span> per month.
      </p>
      {analysis.monthly_capacity != null && (
        <p className="text-sm text-slate-600 mt-1">
          You said you can put away about {formatUSD(analysis.monthly_capacity)}/month.
        </p>
      )}
      {!analysis.feasible && (
        <>
          <p className="text-sm text-amber-900 font-medium mt-2">
            That's short by {formatUSD(analysis.shortfall_per_month)}/month. A few options:
          </p>
          <ul className="list-disc list-inside text-sm text-slate-700 mt-1 space-y-0.5">
            {analysis.options.map((opt, i) => (
              <li key={i}>{opt}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
