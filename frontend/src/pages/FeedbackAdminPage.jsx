import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, Star } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSDate } from '../lib/format'

function downloadCsv(rows) {
  if (!rows.length) return
  const columns = [
    'id', 'created_at', 'workspace_id', 'user_id', 'rating', 'minutes_before', 'minutes_with', 'message',
  ]
  const lines = [columns.join(',')]
  for (const r of rows) {
    lines.push(columns.map((c) => JSON.stringify(r[c] ?? '')).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'missionledger_feedback.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function Stars({ rating }) {
  if (rating == null) return <span className="text-slate-400">—</span>
  return (
    <span className="inline-flex gap-0.5 text-amber-400">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} size={13} fill={n <= rating ? 'currentColor' : 'none'} className={n <= rating ? '' : 'text-slate-300'} />
      ))}
    </span>
  )
}

export default function FeedbackAdminPage() {
  const [summary, setSummary] = useState(null)
  const [rows, setRows] = useState([])
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    api.getFeedbackSummary().then(setSummary).catch((err) => setLoadError(err.message))
    api.listFeedback().then(setRows).catch(() => {})
  }, [])

  if (loadError) {
    return (
      <div className="p-8 text-center max-w-md mx-auto">
        <p className="text-rose-600 font-medium mb-2">Couldn't open Feedback</p>
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
        <h1 className="text-xl font-bold text-slate-900">Feedback</h1>
        <p className="text-sm text-slate-500">What people are telling us, in their own words and numbers.</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Responses</p>
          <p className="text-xl font-bold text-slate-900 tabular-nums tracking-tight mt-0.5">{summary.response_count}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Average rating</p>
          <p className="text-xl font-bold text-slate-900 tabular-nums tracking-tight mt-0.5">
            {summary.avg_rating != null ? `${summary.avg_rating} / 5` : '—'}
          </p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Avg. minutes before</p>
          <p className="text-xl font-bold text-slate-900 tabular-nums tracking-tight mt-0.5">{summary.avg_minutes_before ?? '—'}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Avg. minutes with us</p>
          <p className="text-xl font-bold text-slate-900 tabular-nums tracking-tight mt-0.5">{summary.avg_minutes_with ?? '—'}</p>
        </div>
      </div>

      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
        <p className="text-sm text-emerald-800">
          On average, people say MissionLedger saves them{' '}
          <span className="font-bold">
            {summary.avg_minutes_saved != null ? `${summary.avg_minutes_saved} minutes` : "— not enough answers yet"}
          </span>{' '}
          compared to doing this by hand.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4 overflow-x-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-900">All responses</h2>
          {rows.length > 0 && (
            <button
              onClick={() => downloadCsv(rows)}
              className="text-sm bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg transition inline-flex items-center gap-1.5"
            >
              <Download size={14} /> Download CSV
            </button>
          )}
        </div>
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">No feedback submitted yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200">
                <th className="py-1 pr-3">Date</th>
                <th className="py-1 pr-3">Rating</th>
                <th className="py-1 pr-3">Before</th>
                <th className="py-1 pr-3">With us</th>
                <th className="py-1 pr-3">Saved</th>
                <th className="py-1">Anything else</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 last:border-0 align-top">
                  <td className="py-1.5 pr-3 whitespace-nowrap text-slate-500">{formatUSDate(r.created_at)}</td>
                  <td className="py-1.5 pr-3"><Stars rating={r.rating} /></td>
                  <td className="py-1.5 pr-3">{r.minutes_before ?? '—'}</td>
                  <td className="py-1.5 pr-3">{r.minutes_with ?? '—'}</td>
                  <td className="py-1.5 pr-3">
                    {r.minutes_before != null && r.minutes_with != null ? r.minutes_before - r.minutes_with : '—'}
                  </td>
                  <td className="py-1.5 text-slate-700">{r.message || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
