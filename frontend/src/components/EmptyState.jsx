import { Inbox } from 'lucide-react'

export default function EmptyState({ icon: Icon = Inbox, message, action }) {
  return (
    <div className="text-center py-6 px-4">
      <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-slate-100 text-slate-400 mb-2.5">
        <Icon size={18} strokeWidth={1.75} />
      </div>
      <p className="text-sm text-slate-500">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
