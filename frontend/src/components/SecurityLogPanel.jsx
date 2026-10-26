import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSDate } from '../lib/format'
import EmptyState from './EmptyState'

const DEFENSE_BADGE = {
  Gatekeeper: 'bg-rose-100 text-rose-800',
  'PII Redaction': 'bg-amber-100 text-amber-800',
  'Rate Limiting': 'bg-slate-200 text-slate-800',
  'Number Verification': 'bg-slate-100 text-slate-700',
  'Upload Validation': 'bg-amber-50 text-amber-700',
  'Login Lockout': 'bg-rose-200 text-rose-900',
  'Financial Advice Guard': 'bg-emerald-100 text-emerald-800',
}

export default function SecurityLogPanel({ workspaceId }) {
  const [entries, setEntries] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listSecurityLog(workspaceId).then(setEntries).catch((err) => setError(err.message))
  }, [workspaceId])

  if (error) return <p className="text-sm text-rose-600">{error}</p>
  if (!entries) return <p className="text-sm text-slate-500">Loading…</p>

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        Every time a defense here actually blocked, redacted, throttled, or locked something — not normal activity
        (see the Activity tab for that).
      </p>
      {entries.length === 0 ? (
        <EmptyState icon={ShieldCheck} message="Nothing logged yet — no defense has had to act." />
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl card-shadow divide-y divide-slate-100">
          {entries.map((e) => (
            <div key={e.id} className="px-4 py-2.5 text-sm">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${DEFENSE_BADGE[e.defense] || 'bg-slate-100 text-slate-700'}`}>
                  {e.defense}
                </span>
                <span className="text-xs text-slate-500 uppercase tracking-wide">{e.action}</span>
                {e.user_name && <span className="text-xs text-slate-400">· {e.user_name}</span>}
              </div>
              <p className="text-slate-700">{e.detail}</p>
              <span className="text-xs text-slate-400 block mt-0.5">{formatUSDate(e.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
