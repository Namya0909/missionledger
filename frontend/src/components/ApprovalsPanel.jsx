import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSD, formatUSDate } from '../lib/format'
import EmptyState from './EmptyState'

export default function ApprovalsPanel({ workspaceId, onChanged }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    api
      .listApprovals(workspaceId)
      .then(setItems)
      .finally(() => setLoading(false))
  }

  useEffect(load, [workspaceId])

  function toggle(id) {
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function decide(id, approve, reason) {
    setError('')
    try {
      await api.decideTransaction(workspaceId, id, approve, reason)
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function bulkApprove() {
    setError('')
    try {
      await api.bulkDecide(workspaceId, [...selected], true)
      setSelected(new Set())
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  const decidable = items.filter((i) => i.can_i_decide)

  if (loading) return <p className="text-sm text-slate-500">Loading…</p>

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {decidable.length > 0 && (
        <div className="flex items-center gap-2">
          <button
            onClick={bulkApprove}
            disabled={selected.size === 0}
            className="text-sm bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg disabled:opacity-50"
          >
            Approve selected ({selected.size})
          </button>
          <button
            onClick={() => setSelected(new Set(decidable.map((i) => i.id)))}
            className="text-sm text-emerald-700 hover:underline"
          >
            Select all I can approve
          </button>
        </div>
      )}

      {items.length === 0 && <EmptyState icon={CheckCircle2} message="Nothing is waiting right now." />}

      <div className="space-y-2">
        {items.map((item) => (
          <ApprovalItem
            key={item.id}
            item={item}
            selected={selected.has(item.id)}
            onToggleSelect={() => toggle(item.id)}
            onDecide={decide}
          />
        ))}
      </div>
    </div>
  )
}

function ApprovalItem({ item, selected, onToggleSelect, onDecide }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-3 flex items-start gap-3">
      {item.can_i_decide && (
        <input type="checkbox" checked={selected} onChange={onToggleSelect} className="mt-1.5" />
      )}
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <p className="font-medium text-slate-900">{item.merchant}</p>
          <p className="font-semibold text-slate-900">{formatUSD(item.amount)}</p>
        </div>
        <p className="text-xs text-slate-500">
          {formatUSDate(item.date)} · {item.pot_name} · added by {item.created_by_name}
        </p>
        {item.warnings?.length > 0 && (
          <div className="mt-1 text-xs text-rose-600 space-y-0.5">
            {item.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-1">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {w}
              </div>
            ))}
          </div>
        )}
        {!item.can_i_decide && item.waiting_reason && (
          <p className="mt-1 text-xs text-amber-700">{item.waiting_reason}</p>
        )}
        {!item.can_i_decide && !item.waiting_reason && item.decide_blocked_reason && (
          <p className="mt-1 text-xs text-slate-400">{item.decide_blocked_reason}</p>
        )}

        {item.can_i_decide && !rejecting && (
          <div className="mt-2 flex gap-1">
            <button
              onClick={() => onDecide(item.id, true)}
              className="text-xs bg-emerald-700 hover:bg-emerald-800 text-white px-2 py-1 rounded"
            >
              Approve
            </button>
            <button
              onClick={() => setRejecting(true)}
              className="text-xs bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded"
            >
              Reject
            </button>
          </div>
        )}
        {item.can_i_decide && rejecting && (
          <div className="mt-2 flex gap-1">
            <input
              autoFocus
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason for rejecting"
              className="flex-1 text-xs border border-slate-300 rounded px-2 py-1"
            />
            <button
              onClick={() => reason.trim() && onDecide(item.id, false, reason.trim())}
              disabled={!reason.trim()}
              className="text-xs bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded disabled:opacity-50"
            >
              Confirm
            </button>
            <button onClick={() => setRejecting(false)} className="text-xs text-slate-500 px-2">
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
