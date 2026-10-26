// Shared by CreatePotForm (initial settings) and PotApprovalEditor (editing an
// existing pot). Only rendered for people with manage_pots — enforced again by the
// server regardless.
export default function ApprovalSettingsFields({ members, value, onChange }) {
  const { approval_required, approval_threshold, approver_user_ids } = value

  function toggleApprover(userId) {
    const next = approver_user_ids.includes(userId)
      ? approver_user_ids.filter((id) => id !== userId)
      : [...approver_user_ids, userId]
    onChange({ ...value, approver_user_ids: next })
  }

  return (
    <div className="space-y-3 border border-slate-200 rounded-lg p-3 bg-slate-50">
      <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
        <input
          type="checkbox"
          checked={approval_required}
          onChange={(e) => onChange({ ...value, approval_required: e.target.checked })}
        />
        Approval required
      </label>

      {approval_required && (
        <>
          <label className="block text-sm text-slate-600">
            Only for expenses over $ (optional — leave blank to require approval every time)
            <input
              type="number"
              step="0.01"
              value={approval_threshold ?? ''}
              onChange={(e) => onChange({ ...value, approval_threshold: e.target.value ? Number(e.target.value) : null })}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5"
            />
          </label>

          <div>
            <p className="text-sm text-slate-600 mb-1">Approvers</p>
            <div className="space-y-1">
              {members.map((m) => (
                <label key={m.user.id} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={approver_user_ids.includes(m.user.id)}
                    onChange={() => toggleApprover(m.user.id)}
                  />
                  {m.user.name}
                </label>
              ))}
            </div>
            {approver_user_ids.length === 0 && (
              <p className="text-xs text-rose-600 mt-1">Choose at least one approver.</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
