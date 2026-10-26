import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import ReceiptButton from './ReceiptButton'
import { formatUSD, formatUSDate } from '../lib/format'

const STATUS_STYLE = {
  pending: 'bg-amber-100 text-amber-800',
  approved: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-rose-100 text-rose-800',
}

export default function TransactionCard({ transaction, workspaceId, onDecide, onChanged, onEdit, onDelete }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  return (
    <div className="border border-slate-200 rounded-xl p-3 bg-white card-shadow">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{transaction.merchant}</p>
          <p className="text-xs text-slate-500">
            {formatUSDate(transaction.date)} · {transaction.pot_name} · {transaction.category || '—'}
          </p>
          <p className="text-xs text-slate-400">Added by {transaction.created_by_name}</p>
        </div>
        <p className="font-semibold text-slate-900 whitespace-nowrap tabular-nums">{formatUSD(transaction.amount)}</p>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[transaction.status]}`}>
          {transaction.status}
        </span>
        {transaction.can_i_decide && !rejecting && (
          <div className="flex gap-1">
            <button
              onClick={() => onDecide(transaction.id, true)}
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
      </div>

      {transaction.can_i_decide && rejecting && (
        <div className="mt-2 flex gap-1">
          <input
            autoFocus
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for rejecting"
            className="flex-1 text-xs border border-slate-300 rounded px-2 py-1"
          />
          <button
            onClick={() => reason.trim() && onDecide(transaction.id, false, reason.trim())}
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

      {transaction.warnings?.length > 0 && (
        <div className="mt-2 text-xs text-rose-600 space-y-0.5">
          {transaction.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {w}
            </div>
          ))}
        </div>
      )}
      {transaction.waiting_reason && <div className="mt-1 text-xs text-amber-700">{transaction.waiting_reason}</div>}
      {transaction.rejection_reason && (
        <div className="mt-1 text-xs text-rose-600">Reason: {transaction.rejection_reason}</div>
      )}
      <div className="mt-2 flex items-center justify-between gap-2 flex-wrap">
        <ReceiptButton workspaceId={workspaceId} transaction={transaction} onUploaded={onChanged} />
        {transaction.can_i_edit && !confirmingDelete && (
          <div className="flex gap-2">
            <button onClick={() => onEdit(transaction)} className="text-xs text-emerald-700 hover:underline">
              Edit
            </button>
            <button onClick={() => setConfirmingDelete(true)} className="text-xs text-rose-600 hover:underline">
              Delete
            </button>
          </div>
        )}
        {confirmingDelete && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Delete this expense?</span>
            <button
              onClick={() => onDelete(transaction.id)}
              className="bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded"
            >
              Yes, delete
            </button>
            <button onClick={() => setConfirmingDelete(false)} className="text-slate-500 px-1">
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
