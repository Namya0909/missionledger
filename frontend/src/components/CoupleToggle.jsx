import { useState } from 'react'
import { Heart } from 'lucide-react'
import { api } from '../lib/api'

// Shown only for a 2-person group. Purely optional — confirming just switches the
// icon from outline to filled; declining or ignoring it changes nothing else.
export default function CoupleToggle({ workspaceId, isCouple, onChanged }) {
  const [asking, setAsking] = useState(false)

  async function set(value) {
    await api.setCoupleStatus(workspaceId, value)
    setAsking(false)
    onChanged()
  }

  if (isCouple) {
    return (
      <button title="You've confirmed you're a couple" onClick={() => set(false)}>
        <Heart size={18} className="text-rose-500" fill="currentColor" />
      </button>
    )
  }

  if (asking) {
    return (
      <span className="flex items-center gap-1 text-xs text-slate-500">
        Are you two a couple?
        <button onClick={() => set(true)} className="text-emerald-700 font-medium hover:underline">
          Yes
        </button>
        <button onClick={() => setAsking(false)} className="text-slate-400 hover:underline">
          No
        </button>
      </span>
    )
  }

  return (
    <button title="Let us know if you're a couple (optional)" onClick={() => setAsking(true)} className="opacity-40 hover:opacity-80">
      <Heart size={18} className="text-slate-400" />
    </button>
  )
}
