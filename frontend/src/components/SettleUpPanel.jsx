import { useEffect, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSD, formatUSDate } from '../lib/format'
import EmptyState from './EmptyState'

export default function SettleUpPanel({ workspaceId, members, currentUserId }) {
  const [data, setData] = useState(null)
  const [payments, setPayments] = useState([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)

  function load() {
    api.getSettleUp(workspaceId).then(setData).catch((err) => setError(err.message))
    api.listSettlements(workspaceId).then(setPayments).catch(() => {})
  }

  useEffect(load, [workspaceId])

  async function handleRecord(toUserId, amount, note) {
    await api.recordPayment(workspaceId, { to_user_id: toUserId, amount, note: note || null })
    setShowForm(false)
    load()
  }

  if (error) return <p className="text-sm text-rose-600">{error}</p>
  if (!data) return <p className="text-sm text-slate-500">Loading…</p>

  const otherMembers = members.filter((m) => m.user.id !== currentUserId)

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-slate-900">Balances</h3>
          {otherMembers.length > 0 && (
            <button
              onClick={() => setShowForm((s) => !s)}
              className="text-sm bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg"
            >
              {showForm ? 'Cancel' : '+ Record a payment'}
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500 mb-3">
          Based on every shared pot's split rule — equal, by income, or custom shares — compared
          against what each person has actually paid, minus any payments already recorded below.
        </p>

        {showForm && <RecordPaymentForm members={otherMembers} onRecord={handleRecord} />}

        <div className="bg-white border border-slate-200 rounded-xl card-shadow divide-y divide-slate-100">
          {data.balances.map((b) => (
            <div key={b.user_id} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-sm text-slate-800">{b.name}</span>
              <span className={`text-sm font-semibold ${b.amount > 0.01 ? 'text-emerald-600' : b.amount < -0.01 ? 'text-rose-600' : 'text-slate-400'}`}>
                {b.amount > 0.01 ? `is owed ${formatUSD(b.amount)}` : b.amount < -0.01 ? `owes ${formatUSD(-b.amount)}` : 'all settled'}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="font-semibold text-slate-900 mb-2">Who owes whom</h3>
        {data.transfers.length === 0 ? (
          <EmptyState icon={CheckCircle2} message="Everyone's settled up — no payments needed." />
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl card-shadow divide-y divide-slate-100">
            {data.transfers.map((t, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span>
                  <span className="font-medium text-slate-900">{t.from_name}</span>
                  <span className="text-slate-500"> pays </span>
                  <span className="font-medium text-slate-900">{t.to_name}</span>
                </span>
                <span className="font-semibold text-slate-900">{formatUSD(t.amount)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {payments.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-2">Payment history</h3>
          <div className="bg-white border border-slate-200 rounded-xl card-shadow divide-y divide-slate-100">
            {payments.map((p) => (
              <div key={p.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span>
                  <span className="font-medium text-slate-900">{p.from_name}</span>
                  <span className="text-slate-500"> paid </span>
                  <span className="font-medium text-slate-900">{p.to_name}</span>
                  {p.note && <span className="text-slate-400"> — {p.note}</span>}
                  <span className="text-xs text-slate-400 block">{formatUSDate(p.created_at)}</span>
                </span>
                <span className="font-semibold text-slate-900">{formatUSD(p.amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RecordPaymentForm({ members, onRecord }) {
  const [toUserId, setToUserId] = useState(members[0]?.user.id ?? '')
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await onRecord(Number(toUserId), Number(amount), note)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl card-shadow p-4 mb-3 space-y-2">
      <p className="text-xs text-slate-500">Record money you already sent (e.g. a Venmo) — this reduces what you owe.</p>
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-sm text-slate-600">
          I paid
          <select
            value={toUserId}
            onChange={(e) => setToUserId(e.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 px-2 py-1.5"
          >
            {members.map((m) => (
              <option key={m.user.id} value={m.user.id}>
                {m.user.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-600">
          Amount ($)
          <input
            type="number"
            step="0.01"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="mt-1 block w-28 rounded-lg border border-slate-300 px-2 py-1.5"
          />
        </label>
        <label className="text-sm text-slate-600 flex-1 min-w-[140px]">
          Note (optional)
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-2 py-1.5"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
        >
          {submitting ? 'Saving…' : 'Record'}
        </button>
      </div>
    </form>
  )
}
