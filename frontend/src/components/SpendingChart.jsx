import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TrendingUp } from 'lucide-react'
import EmptyState from './EmptyState'
import { formatUSD } from '../lib/format'

export default function SpendingChart({ transactions }) {
  const byCategory = {}
  for (const t of transactions) {
    if (t.status === 'rejected' || t.amount <= 0) continue
    const key = t.category || 'Uncategorized'
    byCategory[key] = (byCategory[key] || 0) + t.amount
  }
  const data = Object.entries(byCategory)
    .map(([category, total]) => ({ category, total: Math.round(total * 100) / 100 }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 8)

  if (data.length === 0) {
    return <EmptyState icon={TrendingUp} message="No spending yet — add a transaction to see it charted here." />
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
        <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} width={110} />
        <Tooltip formatter={(v) => formatUSD(v)} />
        <Bar dataKey="total" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
