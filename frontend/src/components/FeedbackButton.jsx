import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { MessageSquareText, PartyPopper, Star, X } from 'lucide-react'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import { useAuth } from '../lib/auth.jsx'

const STARS = [1, 2, 3, 4, 5]

// FeedbackButton is mounted once at the app root, outside the <Routes> tree,
// so it can show up on every page — that means it's not nested inside the
// matched Route and can't rely on useParams(). Reading the workspace id out
// of the URL directly works regardless of where this component sits.
function workspaceIdFromPath(pathname) {
  const match = pathname.match(/^\/workspaces\/(\d+)/)
  return match ? Number(match[1]) : null
}

export default function FeedbackButton() {
  const { user } = useAuth()
  const location = useLocation()
  const workspaceId = workspaceIdFromPath(location.pathname)
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState(0)
  const [minutesBefore, setMinutesBefore] = useState('')
  const [minutesWith, setMinutesWith] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  if (!user) return null

  function reset() {
    setRating(0)
    setMinutesBefore('')
    setMinutesWith('')
    setMessage('')
    setError('')
    setSent(false)
  }

  function close() {
    setOpen(false)
    setTimeout(reset, 200)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await api.submitFeedback({
        workspace_id: workspaceId,
        rating: rating || null,
        minutes_before: minutesBefore === '' ? null : Number(minutesBefore),
        minutes_with: minutesWith === '' ? null : Number(minutesWith),
        message: message || null,
      })
      setSent(true)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 left-4 z-40 bg-white border border-slate-200 card-shadow text-slate-700 hover:text-emerald-700 hover:border-emerald-300 px-3 py-2 rounded-full text-sm font-medium flex items-center gap-1.5"
      >
        <MessageSquareText size={15} /> Feedback
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
          <div className="bg-white rounded-xl card-shadow border border-slate-200 w-full max-w-sm p-6">
            {sent ? (
              <div className="text-center py-4">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 text-emerald-700 mb-2">
                  <PartyPopper size={22} strokeWidth={1.75} />
                </div>
                <p className="font-semibold text-slate-900 mb-1">Thanks for the feedback!</p>
                <p className="text-sm text-slate-500 mb-4">It genuinely helps shape what we build next.</p>
                <button onClick={close} className="text-sm text-emerald-700 hover:underline font-medium">
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-slate-900">Share your feedback</h2>
                  <button type="button" onClick={close} className="text-slate-400 hover:text-slate-600">
                    <X size={18} />
                  </button>
                </div>

                <div>
                  <p className="text-sm text-slate-600 mb-1.5">How would you rate your experience?</p>
                  <div className="flex gap-1">
                    {STARS.map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setRating(n)}
                        className={n <= rating ? 'text-amber-400' : 'text-slate-300'}
                        aria-label={`${n} star${n > 1 ? 's' : ''}`}
                      >
                        <Star size={22} fill={n <= rating ? 'currentColor' : 'none'} />
                      </button>
                    ))}
                  </div>
                </div>

                <label className="block text-sm text-slate-600">
                  How many minutes did this take you before MissionLedger?
                  <input
                    type="number"
                    min="0"
                    value={minutesBefore}
                    onChange={(e) => setMinutesBefore(e.target.value)}
                    placeholder="e.g. 30"
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </label>

                <label className="block text-sm text-slate-600">
                  How many minutes with MissionLedger?
                  <input
                    type="number"
                    min="0"
                    value={minutesWith}
                    onChange={(e) => setMinutesWith(e.target.value)}
                    placeholder="e.g. 5"
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </label>

                <label className="block text-sm text-slate-600">
                  Anything else?
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </label>

                {error && (
                  <p className="text-sm text-rose-600">
                    {error} <button type="submit" className="text-emerald-700 hover:underline font-medium">Try again</button>
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {submitting ? 'Sending…' : 'Send feedback'}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  )
}
