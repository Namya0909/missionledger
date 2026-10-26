import { useState } from 'react'
import ApprovalSettingsFields from './ApprovalSettingsFields'
import { api } from '../lib/api'

export default function PotApprovalEditor({ workspaceId, pot, members, onSaved, onCancel }) {
  const [value, setValue] = useState({
    approval_required: pot.approval_required,
    approval_threshold: pot.approval_threshold,
    approver_user_ids: pot.approver_user_ids || [],
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setError('')
    if (value.approval_required && value.approver_user_ids.length === 0) {
      setError('Choose at least one approver, or turn approval off.')
      return
    }
    setSaving(true)
    try {
      await api.updatePotApproval(workspaceId, pot.id, value)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-3 space-y-2">
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <ApprovalSettingsFields members={members} value={value} onChange={setValue} />
      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="text-xs bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1 rounded disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel} className="text-xs text-slate-600 hover:bg-slate-100 px-3 py-1 rounded">
          Cancel
        </button>
      </div>
    </div>
  )
}
