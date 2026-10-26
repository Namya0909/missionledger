import { ROLE_LABELS } from '../lib/permissions'

export default function SetupInviteRow({ invite, included, onToggleIncluded, onChangeLabel }) {
  return (
    <div className="flex items-center gap-3 bg-white border border-slate-200 rounded-lg px-3 py-2">
      <input
        type="checkbox"
        checked={included}
        onChange={(e) => onToggleIncluded(e.target.checked)}
        className="h-4 w-4 shrink-0"
      />
      <div className="flex-1 min-w-0">
        <input
          value={invite.label}
          onChange={(e) => onChangeLabel(e.target.value)}
          disabled={!included}
          className="text-sm font-medium text-slate-800 w-full rounded-lg border border-transparent hover:border-slate-200 focus:border-slate-300 px-1 py-0.5 disabled:opacity-50 disabled:bg-transparent"
        />
        {invite.note && <p className="text-xs text-slate-400">{invite.note}</p>}
      </div>
      <span className="text-xs text-slate-500 shrink-0">{ROLE_LABELS[invite.role] || invite.role}</span>
    </div>
  )
}
