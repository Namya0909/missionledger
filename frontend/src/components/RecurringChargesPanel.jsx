import { useEffect, useState } from 'react'
import { Repeat } from 'lucide-react'
import { api } from '../lib/api'
import { formatUSD } from '../lib/format'
import EmptyState from './EmptyState'

export default function RecurringChargesPanel({ workspaceId, pots, canCreate }) {
  const [charges, setCharges] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')

  function load() {
    api.listRecurring(workspaceId).then(setCharges).catch((err) => setError(err.message))
  }

  useEffect(load, [workspaceId])

  async function handleCreate(payload) {
    await api.createRecurring(workspaceId, payload)
    setShowForm(false)
    load()
  }

  async function handleRemove(id) {
    await api.deleteRecurring(workspaceId, id)
    load()
  }

  const active = charges.filter((c) => c.active)

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-slate-900">Recurring Charges</h3>
        {canCreate && (
          <button onClick={() => setShowForm((s) => !s)} className="text-sm text-emerald-700 hover:underline">
            {showForm ? 'Cancel' : '+ Add recurring charge'}
          </button>
        )}
      </div>
      <p className="text-xs text-slate-500 mb-3">
        A fixed monthly bill (rent, a subscription) that adds itself automatically each month —
        no need to re-type it, and it still goes through the pot's own approval rules.
      </p>
      {error && <p className="text-xs text-rose-600 mb-2">{error}</p>}
      {showForm && <RecurringChargeForm pots={pots} onCreate={handleCreate} />}

      {active.length === 0 ? (
        <EmptyState icon={Repeat} message="No recurring charges set up — add rent or a subscription above." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {active.map((c) => (
            <li key={c.id} className="py-2 flex items-center justify-between text-sm">
              <div>
                <p className="font-medium text-slate-900">{c.merchant}</p>
                <p className="text-xs text-slate-500">
                  {c.pot_name} · day {c.day_of_month} of each month
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-900">{formatUSD(c.amount)}</span>
                {canCreate && (
                  <button onClick={() => handleRemove(c.id)} className="text-xs text-rose-600 hover:underline">
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function RecurringChargeForm({ pots, onCreate }) {
  const [form, setForm] = useState({ pot_id: pots[0]?.id ?? '', merchant: '', amount: '', category: '', day_of_month: 1 })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await onCreate({
        pot_id: Number(form.pot_id),
        merchant: form.merchant,
        amount: Number(form.amount),
        category: form.category || null,
        day_of_month: Number(form.day_of_month),
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border border-slate-200 rounded-lg p-3 mb-3 space-y-2 bg-slate-50">
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <select
          value={form.pot_id}
          onChange={(e) => set('pot_id', e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        >
          {pots.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          required
          placeholder="Merchant"
          value={form.merchant}
          onChange={(e) => set('merchant', e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        />
        <input
          required
          type="number"
          step="0.01"
          placeholder="Amount ($)"
          value={form.amount}
          onChange={(e) => set('amount', e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5 w-28"
        />
        <input
          placeholder="Category"
          value={form.category}
          onChange={(e) => set('category', e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        />
        <label className="text-sm text-slate-600 flex items-center gap-1">
          Day
          <input
            type="number"
            min="1"
            max="28"
            value={form.day_of_month}
            onChange={(e) => set('day_of_month', e.target.value)}
            className="w-16 rounded-lg border border-slate-300 px-2 py-1.5"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
        >
          {submitting ? 'Adding…' : 'Add'}
        </button>
      </div>
    </form>
  )
}
