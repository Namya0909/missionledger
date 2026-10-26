import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, BarChart3 } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import { api } from '../lib/api'
import { formatUSD } from '../lib/format'

const SERIES_COLORS = ['#059669', '#0ea5e9', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

function pivotDaily(rows) {
  const purposes = [...new Set(rows.map((r) => r.purpose))]
  const byDate = {}
  for (const r of rows) {
    const bucket = byDate[r.date] || (byDate[r.date] = { date: r.date })
    bucket[r.purpose] = r.tokens
  }
  const data = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  return { purposes, data }
}

function downloadCsv(rows) {
  if (!rows.length) return
  const columns = [
    'id', 'request_id', 'purpose', 'workspace_id', 'user_id',
    'input_tokens', 'cached_tokens', 'output_tokens', 'cost_usd', 'created_at',
  ]
  const lines = [columns.join(',')]
  for (const r of rows) {
    lines.push(columns.map((c) => JSON.stringify(r[c] ?? '')).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'missionledger_ai_usage.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function CostsPage() {
  const [summary, setSummary] = useState(null)
  const [daily, setDaily] = useState([])
  const [flags, setFlags] = useState([])
  const [loadError, setLoadError] = useState('')
  const [flagError, setFlagError] = useState('')

  useEffect(() => {
    api.getCostsSummary().then(setSummary).catch((err) => setLoadError(err.message))
    api.getCostsDaily(30).then(setDaily).catch(() => {})
    api.listFeatureFlags().then(setFlags).catch(() => {})
  }, [])

  const { purposes, data: dailyData } = useMemo(() => pivotDaily(daily), [daily])

  async function toggleFlag(name, enabled) {
    setFlagError('')
    const prev = flags
    setFlags((fs) => fs.map((f) => (f.name === name ? { ...f, enabled } : f)))
    try {
      await api.setFeatureFlag(name, enabled)
    } catch (err) {
      setFlags(prev)
      setFlagError(err.message)
    }
  }

  async function handleDownloadCsv() {
    try {
      const rows = await api.getCostsRaw()
      downloadCsv(rows)
    } catch (err) {
      setLoadError(err.message)
    }
  }

  if (loadError) {
    return (
      <div className="p-8 text-center max-w-md mx-auto">
        <p className="text-rose-600 font-medium mb-2">Couldn't open the Costs page</p>
        <p className="text-sm text-slate-500 mb-4">{loadError}</p>
        <Link to="/" className="text-emerald-700 text-sm hover:underline">
          ← Back to your workspaces
        </Link>
      </div>
    )
  }
  if (!summary) return <div className="p-8 text-center text-slate-500">Loading…</div>

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">AI costs</h1>
        <p className="text-sm text-slate-500">
          Every number below is computed in Python from real token counts the AI provider returned —
          nothing here is estimated.
        </p>
      </div>

      {summary.pricing_is_placeholder && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3 flex gap-2">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" />
          <span>
            Prices for <code>{summary.model_name}</code> in <code>config.py</code>'s <code>MODEL_PRICING</code> are a
            placeholder — the real per-token rate hasn't been confirmed yet, so every dollar figure here will be off by
            whatever factor that placeholder is wrong by. Token counts themselves are real.
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Total requests" value={summary.total_requests.toLocaleString('en-US')} />
        <Tile label="Total AI calls" value={summary.total_calls.toLocaleString('en-US')} />
        <Tile label="Avg cost / request" value={`$${summary.avg_cost_per_request.toFixed(4)}`} />
        <Tile
          label="Cache hit rate"
          value={`${summary.cache_hit_rate_pct}%`}
          sub={`${summary.total_cached_tokens.toLocaleString('en-US')} of ${summary.total_input_tokens.toLocaleString('en-US')} input tokens cached`}
        />
        <Tile label="This month's cost" value={formatUSD(summary.this_month_cost_usd)} />
        <Tile label="Active users this month" value={summary.this_month_active_users.toLocaleString('en-US')} />
        <Tile label="Cost / user / month" value={`$${summary.cost_per_user_this_month.toFixed(4)}`} />
        <Tile
          label="Total tokens"
          value={(summary.total_input_tokens + summary.total_output_tokens).toLocaleString('en-US')}
        />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <h2 className="font-semibold text-slate-900 mb-1">Projected monthly cost</h2>
        <p className="text-xs text-slate-500 mb-3">
          Linear estimate from this month's real cost-per-user figure — not a guarantee.
        </p>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(summary.projections).map(([n, cost]) => (
            <div key={n} className="bg-slate-50 rounded-lg p-3 text-center">
              <p className="text-xs text-slate-500">{Number(n).toLocaleString('en-US')} users</p>
              <p className="text-lg font-bold text-slate-900">{formatUSD(cost)}/mo</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4 overflow-x-auto">
        <h2 className="font-semibold text-slate-900 mb-3">By workspace type</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="py-1 pr-2">Type</th>
              <th className="py-1 pr-2 text-right">Calls</th>
              <th className="py-1 pr-2 text-right">Tokens</th>
              <th className="py-1 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {summary.by_workspace_type.map((row) => (
              <tr key={row.workspace_type} className="border-b border-slate-100 last:border-0">
                <td className="py-1 pr-2">{row.workspace_type}</td>
                <td className="py-1 pr-2 text-right">{row.calls.toLocaleString('en-US')}</td>
                <td className="py-1 pr-2 text-right">{row.tokens.toLocaleString('en-US')}</td>
                <td className="py-1 text-right">{formatUSD(row.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-900">Tokens per day by agent</h2>
          <button
            onClick={handleDownloadCsv}
            className="text-sm bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg transition"
          >
            Download CSV
          </button>
        </div>
        {dailyData.length === 0 ? (
          <EmptyState icon={BarChart3} message="No AI usage logged in the last 30 days yet — ask the assistant a question in any workspace to see it here." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {purposes.map((p, i) => (
                <Bar key={p} dataKey={p} stackId="tokens" fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <h2 className="font-semibold text-slate-900 mb-1">Savings (toggle to compare)</h2>
        <p className="text-xs text-slate-500 mb-3">
          Each switch is a real, independent code path — off reproduces the naive baseline so you can measure the
          difference.
        </p>
        {flagError && <p className="text-sm text-rose-600 mb-2">{flagError}</p>}
        <div className="divide-y divide-slate-100">
          {flags.map((f) => (
            <label key={f.name} className="flex items-start gap-3 py-2 cursor-pointer">
              <input
                type="checkbox"
                checked={f.enabled}
                onChange={(e) => toggleFlag(f.name, e.target.checked)}
                className="mt-1"
              />
              <span>
                <span className="block text-sm font-medium text-slate-800">{f.name}</span>
                <span className="block text-xs text-slate-500">{f.description}</span>
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}

function Tile({ label, value, sub }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="text-xl font-bold text-slate-900 tabular-nums tracking-tight mt-0.5">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}
