import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, Star } from 'lucide-react'
import { api } from '../lib/api'
import { FEEDBACK_SETS, REVIEWER_ROLES } from '../lib/feedbackQuestions'
import { formatUSDate } from '../lib/format'

const ROLE_LABEL = Object.fromEntries(REVIEWER_ROLES.map((r) => [r.key, r.label]))

// All structured-answer question keys across every role, in a stable order, so
// the CSV has one column per question (blank where that row's role didn't ask it).
const ALL_QUESTION_KEYS = Object.values(FEEDBACK_SETS).flatMap((set) => set.questions.map((q) => q.key))

function questionLabel(key) {
  for (const set of Object.values(FEEDBACK_SETS)) {
    const q = set.questions.find((q) => q.key === key)
    if (q) return q.label
  }
  return key
}

function downloadCsv(rows) {
  if (!rows.length) return
  const columns = [
    'id', 'created_at', 'workspace_id', 'user_id', 'reviewer_role', 'rating', 'minutes_before', 'minutes_with', 'message',
    ...ALL_QUESTION_KEYS,
  ]
  const lines = [columns.join(',')]
  for (const r of rows) {
    const values = columns.map((c) => {
      if (ALL_QUESTION_KEYS.includes(c)) return JSON.stringify(r.structured_answers?.[c] ?? '')
      return JSON.stringify(r[c] ?? '')
    })
    lines.push(values.join(','))
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
          {Object.keys(summary.by_role || {}).length > 0 && (
            <p className="text-[11px] text-slate-400 mt-1">
              {Object.entries(summary.by_role)
                .map(([role, count]) => `${count} ${ROLE_LABEL[role] || role}`)
                .join(' · ')}
            </p>
          )}
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
          <ul className="space-y-4">
            {rows.map((r) => (
              <li key={r.id} className="border-b border-slate-100 last:border-0 pb-4 last:pb-0">
                <div className="flex items-center justify-between flex-wrap gap-y-1 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                      {ROLE_LABEL[r.reviewer_role] || 'Just trying it out'}
                    </span>
                    <Stars rating={r.rating} />
                  </div>
                  <span className="text-xs text-slate-400">{formatUSDate(r.created_at)}</span>
                </div>

                {(r.minutes_before != null || r.minutes_with != null) && (
                  <p className="text-xs text-slate-500 mb-1.5">
                    Before: {r.minutes_before ?? '—'} min · With us: {r.minutes_with ?? '—'} min
                    {r.minutes_before != null && r.minutes_with != null && (
                      <> · Saved: {r.minutes_before - r.minutes_with} min</>
                    )}
                  </p>
                )}

                {r.message && <p className="text-sm text-slate-700 mb-1.5">{r.message}</p>}

                {r.structured_answers && Object.keys(r.structured_answers).length > 0 && (
                  <dl className="space-y-1.5 mt-2">
                    {Object.entries(r.structured_answers).map(([key, answer]) => (
                      <div key={key} className="text-sm">
                        <dt className="text-xs font-medium text-slate-500">{questionLabel(key)}</dt>
                        <dd className="text-slate-700">{typeof answer === 'number' ? `${answer} / 5` : answer || '—'}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
