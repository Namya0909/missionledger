import { useState } from 'react'
import { friendlyError } from '../lib/friendlyError'

// Doubles as the edit form — pass `transaction` + `onSave` to prefill and edit an
// existing expense instead of creating a new one; everything else (fields, AI
// category suggestion wording) stays the same except AI review only runs on create.
export default function CreateTransactionForm({ pots, onCreate, onCancel, transaction, onSave }) {
  const isEdit = Boolean(transaction)
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState(
    isEdit
      ? {
          pot_id: transaction.pot_id,
          date: transaction.date,
          merchant: transaction.merchant,
          description: transaction.description || '',
          amount: transaction.amount,
          category: transaction.category || '',
        }
      : {
          pot_id: pots[0]?.id ?? '',
          date: today,
          merchant: '',
          description: '',
          amount: '',
          category: '',
        }
  )
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    const payload = {
      pot_id: Number(form.pot_id),
      date: form.date,
      merchant: form.merchant,
      description: form.description || null,
      amount: Number(form.amount),
      category: form.category || null,
    }
    try {
      await (isEdit ? onSave(payload) : onCreate(payload))
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl card-shadow p-5 space-y-3">
      <h3 className="font-semibold text-slate-900">{isEdit ? 'Edit Transaction' : 'New Transaction'}</h3>
      {!isEdit && (
        <p className="text-xs text-slate-500">
          MissionLedger's AI will suggest a category and flag any rule violations before this goes to
          approval.
        </p>
      )}
      {error && (
        <p className="text-sm text-rose-600">
          {error} <button type="submit" className="text-emerald-700 hover:underline font-medium">Try again</button>
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm text-slate-600 col-span-2">
          Pot
          <select
            required
            value={form.pot_id}
            onChange={(e) => set('pot_id', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          >
            {pots.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-slate-600">
          Date
          <input
            type="date"
            required
            value={form.date}
            onChange={(e) => set('date', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600">
          Amount ($)
          <input
            type="number"
            step="0.01"
            required
            value={form.amount}
            onChange={(e) => set('amount', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600 col-span-2">
          Merchant / store
          <input
            required
            value={form.merchant}
            onChange={(e) => set('merchant', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600 col-span-2">
          Description
          <input
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600 col-span-2">
          Category{!isEdit && ' (leave blank to let the AI suggest one)'}
          <input
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>
      </div>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={submitting || !pots.length}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {isEdit ? (submitting ? 'Saving…' : 'Save changes') : submitting ? 'Reviewing with AI…' : 'Add Transaction'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
