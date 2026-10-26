import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatUSD } from '../lib/format'

export default function AIUsageChart({ usage }) {
  if (!usage.length) {
    return <p className="text-sm text-slate-500">No AI calls logged yet for this workspace.</p>
  }

  const totalCost = usage.reduce((sum, u) => sum + u.cost_usd, 0)
  const totalTokens = usage.reduce((sum, u) => sum + u.input_tokens + u.output_tokens, 0)

  const chartData = usage
    .slice()
    .reverse()
    .map((u, i) => ({
      name: `#${i + 1}`,
      cost: Number(u.cost_usd.toFixed(5)),
    }))

  return (
    <div>
      <div className="flex gap-6 mb-4">
        <div>
          <p className="text-xs text-slate-500">Total AI calls</p>
          <p className="text-xl font-bold text-slate-900">{usage.length}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total tokens</p>
          <p className="text-xl font-bold text-slate-900">{totalTokens.toLocaleString('en-US')}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total cost</p>
          <p className="text-xl font-bold text-slate-900">{formatUSD(totalCost)}</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip formatter={(v) => formatUSD(v)} />
          <Bar dataKey="cost" fill="#059669" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
