import { useState } from 'react'
import ApprovalSettingsFields from './ApprovalSettingsFields'
import { POT_TYPE_LABELS, SPLIT_METHOD_LABELS } from '../lib/permissions'

const POT_TYPES = Object.entries(POT_TYPE_LABELS).map(([value, label]) => ({ value, label }))

function splitCategories(text) {
  const items = text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  return items.length ? items : null
}

export default function CreatePotForm({ onCreate, onCancel, isGroup, members }) {
  const [form, setForm] = useState({
    name: '',
    type: 'spending',
    budget_or_grant_amount: '',
    target_amount: '',
    deadline: '',
    monthly_limit: '',
    allowed_categories: '',
    disallowed_categories: '',
    grantor: '',
    start_date: '',
    end_date: '',
    split_method: '',
  })
  const [customShares, setCustomShares] = useState({}) // user_id -> percent (0-100)
  const [approval, setApproval] = useState({ approval_required: true, approval_threshold: null, approver_user_ids: [] })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  const customTotal = Object.values(customShares).reduce((sum, v) => sum + (Number(v) || 0), 0)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (approval.approval_required && approval.approver_user_ids.length === 0) {
      setError('Choose at least one approver, or turn approval off.')
      return
    }
    if (form.split_method === 'custom' && Math.round(customTotal) !== 100) {
      setError(`Custom shares must add up to 100% (currently ${customTotal}%).`)
      return
    }

    setSubmitting(true)
    try {
      await onCreate({
        name: form.name,
        type: form.type,
        budget_or_grant_amount: form.budget_or_grant_amount ? Number(form.budget_or_grant_amount) : null,
        target_amount: form.target_amount ? Number(form.target_amount) : null,
        deadline: form.deadline || null,
        monthly_limit: form.monthly_limit ? Number(form.monthly_limit) : null,
        allowed_categories: splitCategories(form.allowed_categories),
        disallowed_categories: splitCategories(form.disallowed_categories),
        grantor: form.grantor || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        split_method: form.split_method || null,
        custom_shares:
          form.split_method === 'custom'
            ? Object.fromEntries(Object.entries(customShares).map(([uid, pct]) => [uid, (Number(pct) || 0) / 100]))
            : null,
        approval_required: approval.approval_required,
        approval_threshold: approval.approval_threshold,
        approver_user_ids: approval.approver_user_ids,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl card-shadow p-5 space-y-3">
      <h3 className="font-semibold text-slate-900">New Pot</h3>
      {error && <p className="text-sm text-rose-600">{error}</p>}

      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm text-slate-600 col-span-2">
          Name
          <input
            required
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600 col-span-2">
          Type
          <select
            value={form.type}
            onChange={(e) => set('type', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          >
            {POT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-slate-600">
          Budget / grant amount ($)
          <input
            type="number"
            step="0.01"
            value={form.budget_or_grant_amount}
            onChange={(e) => set('budget_or_grant_amount', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600">
          Monthly limit ($)
          <input
            type="number"
            step="0.01"
            value={form.monthly_limit}
            onChange={(e) => set('monthly_limit', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        {form.type === 'savings_goal' && (
          <>
            <label className="text-sm text-slate-600">
              Target amount ($)
              <input
                type="number"
                step="0.01"
                value={form.target_amount}
                onChange={(e) => set('target_amount', e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
              />
            </label>
            <label className="text-sm text-slate-600">
              Deadline
              <input
                type="date"
                value={form.deadline}
                onChange={(e) => set('deadline', e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
              />
            </label>
          </>
        )}

        {form.type === 'restricted_grant' && (
          <label className="text-sm text-slate-600 col-span-2">
            Grantor
            <input
              value={form.grantor}
              onChange={(e) => set('grantor', e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
            />
          </label>
        )}

        <label className="text-sm text-slate-600">
          Start date
          <input
            type="date"
            value={form.start_date}
            onChange={(e) => set('start_date', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>
        <label className="text-sm text-slate-600">
          End date
          <input
            type="date"
            value={form.end_date}
            onChange={(e) => set('end_date', e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>

        <label className="text-sm text-slate-600 col-span-2">
          Allowed categories (comma separated)
          <input
            value={form.allowed_categories}
            onChange={(e) => set('allowed_categories', e.target.value)}
            placeholder="Groceries, Utilities"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>
        <label className="text-sm text-slate-600 col-span-2">
          Disallowed categories (comma separated)
          <input
            value={form.disallowed_categories}
            onChange={(e) => set('disallowed_categories', e.target.value)}
            placeholder="Entertainment, Alcohol"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
          />
        </label>
      </div>

      {isGroup && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          <label className="text-sm text-slate-600 block">
            Split this pot's cost
            <select
              value={form.split_method}
              onChange={(e) => set('split_method', e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
            >
              <option value="">Not shared — just one pot (no splitting)</option>
              {Object.entries(SPLIT_METHOD_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {form.split_method === 'custom' && (
            <div className="space-y-1">
              <p className="text-xs text-slate-500">Each person's share, in percent (must total 100%).</p>
              {members.map((m) => (
                <label key={m.user.id} className="flex items-center justify-between text-sm text-slate-700 gap-2">
                  {m.user.name}
                  <input
                    type="number"
                    value={customShares[m.user.id] ?? ''}
                    onChange={(e) => setCustomShares((s) => ({ ...s, [m.user.id]: e.target.value }))}
                    className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-right"
                  />
                </label>
              ))}
              <p className={`text-xs ${Math.round(customTotal) === 100 ? 'text-emerald-600' : 'text-amber-600'}`}>
                Total: {customTotal}%
              </p>
            </div>
          )}
        </div>
      )}

      <div className="border-t border-slate-100 pt-3">
        <ApprovalSettingsFields members={members} value={approval} onChange={setApproval} />
      </div>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={submitting}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {submitting ? 'Creating…' : 'Create Pot'}
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
