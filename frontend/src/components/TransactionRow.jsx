import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import ReceiptButton from './ReceiptButton'
import { formatUSD, formatUSDate } from '../lib/format'

const STATUS_STYLE = {
  pending: 'bg-amber-100 text-amber-800',
  approved: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-rose-100 text-rose-800',
}

export default function TransactionRow({ transaction, workspaceId, onDecide, onChanged, onEdit, onDelete }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  return (
    <tr className="border-b border-slate-100 last:border-0 align-top">
      <td className="py-2 pr-4 text-sm text-slate-600 whitespace-nowrap">
        {formatUSDate(transaction.date)}
      </td>
      <td className="py-2 pr-4 text-sm font-medium text-slate-900">{transaction.merchant}</td>
      <td className="py-2 pr-4 text-sm text-slate-600">{transaction.pot_name}</td>
      <td className="py-2 pr-4 text-sm text-slate-600">{transaction.category || '—'}</td>
      <td className="py-2 pr-4 text-sm text-slate-600">{transaction.created_by_name}</td>
      <td className="py-2 pr-4 text-sm font-semibold text-slate-900 text-right tabular-nums">
        {formatUSD(transaction.amount)}
      </td>
      <td className="py-2 pr-4">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[transaction.status]}`}>
          {transaction.status}
        </span>
        {transaction.warnings?.length > 0 && (
          <div className="mt-1 text-xs text-rose-600 space-y-0.5">
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
        <div className="mt-1">
          <ReceiptButton workspaceId={workspaceId} transaction={transaction} onUploaded={onChanged} />
        </div>
        {transaction.can_i_edit && !confirmingDelete && (
          <div className="mt-1 flex gap-2">
            <button onClick={() => onEdit(transaction)} className="text-xs text-emerald-700 hover:underline">
              Edit
            </button>
            <button onClick={() => setConfirmingDelete(true)} className="text-xs text-rose-600 hover:underline">
              Delete
            </button>
          </div>
        )}
        {confirmingDelete && (
          <div className="mt-1 flex items-center gap-2 text-xs">
            <span className="text-slate-500">Delete?</span>
            <button
              onClick={() => onDelete(transaction.id)}
              className="bg-rose-600 hover:bg-rose-700 text-white px-2 py-0.5 rounded"
            >
              Yes
            </button>
            <button onClick={() => setConfirmingDelete(false)} className="text-slate-500 px-1">
              Cancel
            </button>
          </div>
        )}
      </td>
      <td className="py-2 text-right min-w-[140px]">
        {transaction.can_i_decide && !rejecting && (
          <div className="flex gap-1 justify-end">
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
        {transaction.can_i_decide && rejecting && (
          <div className="flex flex-col gap-1 items-end">
            <input
              autoFocus
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason for rejecting"
              className="text-xs border border-slate-300 rounded px-2 py-1 w-40"
            />
            <div className="flex gap-1">
              <button
                onClick={() => reason.trim() && onDecide(transaction.id, false, reason.trim())}
                disabled={!reason.trim()}
                className="text-xs bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded disabled:opacity-50"
              >
                Confirm
              </button>
              <button onClick={() => setRejecting(false)} className="text-xs text-slate-500 px-2 py-1">
                Cancel
              </button>
            </div>
          </div>
        )}
      </td>
    </tr>
  )
}
