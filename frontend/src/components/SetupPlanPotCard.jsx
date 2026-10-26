import { useState } from 'react'
import { POT_TYPE_LABELS, SPLIT_METHOD_LABELS } from '../lib/permissions'

const POT_TYPES = Object.entries(POT_TYPE_LABELS)

function categoriesToText(categories) {
  return (categories || []).join(', ')
}

function textToCategories(text) {
  return text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

export default function SetupPlanPotCard({ pot, onChange, onRemove, isGroup }) {
  const [categoriesText, setCategoriesText] = useState(categoriesToText(pot.allowed_categories))

  function set(field, value) {
    onChange({ ...pot, [field]: value })
  }

  function handleTypeChange(newType) {
    onChange({
      ...pot,
      type: newType,
      budget_or_grant_amount: null,
      target_amount: null,
      deadline: null,
      monthly_limit: null,
    })
  }

  const deadlineLabel =
    pot.type === 'savings_goal' ? 'Target date' : pot.type === 'restricted_grant' ? 'Grant ends' : null

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <input
          value={pot.name}
          onChange={(e) => set('name', e.target.value)}
          className="font-semibold text-slate-900 text-sm flex-1 rounded-lg border border-transparent hover:border-slate-200 focus:border-slate-300 px-2 py-1 -ml-2"
        />
        <button
          type="button"
          onClick={onRemove}
          className="text-xs text-slate-400 hover:text-rose-600 px-1"
          title="Remove this pot"
        >
          Remove
        </button>
      </div>

      <label className="block text-xs text-slate-500">
        Type
        <select
          value={pot.type}
          onChange={(e) => handleTypeChange(e.target.value)}
          className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
        >
          {POT_TYPES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-2">
        {pot.type === 'savings_goal' && (
          <label className="text-xs text-slate-500">
            Goal amount ($)
            <input
              type="number"
              step="0.01"
              value={pot.target_amount ?? ''}
              onChange={(e) => set('target_amount', e.target.value ? Number(e.target.value) : null)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
            />
          </label>
        )}
        {pot.type === 'restricted_grant' && (
          <label className="text-xs text-slate-500">
            Grant amount ($)
            <input
              type="number"
              step="0.01"
              value={pot.budget_or_grant_amount ?? ''}
              onChange={(e) => set('budget_or_grant_amount', e.target.value ? Number(e.target.value) : null)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
            />
          </label>
        )}
        {pot.type === 'spending' && (
          <label className="text-xs text-slate-500">
            Monthly budget ($)
            <input
              type="number"
              step="0.01"
              value={pot.monthly_limit ?? ''}
              onChange={(e) => set('monthly_limit', e.target.value ? Number(e.target.value) : null)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
            />
          </label>
        )}
        {pot.type === 'reserve' && (
          <label className="text-xs text-slate-500">
            Expected monthly contribution ($)
            <input
              type="number"
              step="0.01"
              value={pot.monthly_limit ?? ''}
              onChange={(e) => set('monthly_limit', e.target.value ? Number(e.target.value) : null)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
            />
          </label>
        )}
        {deadlineLabel && (
          <label className="text-xs text-slate-500">
            {deadlineLabel}
            <input
              type="date"
              value={pot.deadline ?? ''}
              onChange={(e) => set('deadline', e.target.value || null)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
            />
          </label>
        )}
      </div>

      {pot.type === 'restricted_grant' && (
        <label className="block text-xs text-slate-500">
          Allowed categories (comma separated)
          <input
            value={categoriesText}
            onChange={(e) => {
              setCategoriesText(e.target.value)
              set('allowed_categories', textToCategories(e.target.value))
            }}
            placeholder="Food, Supplies"
            className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
      )}

      {isGroup && pot.type !== 'reserve' && (
        <label className="block text-xs text-slate-500">
          Split this pot's cost
          <select
            value={pot.split_method ?? ''}
            onChange={(e) => set('split_method', e.target.value || null)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">Not shared</option>
            {Object.entries(SPLIT_METHOD_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="flex items-center justify-between text-xs text-slate-600 border-t border-slate-100 pt-2">
        <span>Needs approval before it counts</span>
        <input
          type="checkbox"
          checked={pot.approval_required}
          onChange={(e) => set('approval_required', e.target.checked)}
          className="h-4 w-4"
        />
      </label>
      {pot.approval_required && pot.approval_reason && (
        <p className="text-xs text-slate-400 italic">{pot.approval_reason}</p>
      )}
    </div>
  )
}
