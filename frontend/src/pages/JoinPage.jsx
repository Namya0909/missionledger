import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../lib/auth.jsx'
import { api } from '../lib/api'
import { ROLE_LABELS, WORKSPACE_TYPE_LABELS } from '../lib/permissions'

export default function JoinPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(!!token)
  const [joining, setJoining] = useState(false)
  const [codeInput, setCodeInput] = useState('')

  useEffect(() => {
    if (!token) return
    api
      .getInvitePreview(token)
      .then(setPreview)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  function handleCodeSubmit(e) {
    e.preventDefault()
    const code = codeInput.trim()
    if (code) navigate(`/join/${encodeURIComponent(code)}`)
  }

  async function handleJoin() {
    setJoining(true)
    setError('')
    try {
      const res = await api.acceptInvite(token)
      navigate(`/workspaces/${res.workspace_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setJoining(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <form onSubmit={handleCodeSubmit} className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-sm">
          <h1 className="text-xl font-bold text-slate-900 mb-1">Join a workspace</h1>
          <p className="text-sm text-slate-500 mb-5">Enter the join code someone shared with you.</p>
          <input
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value.toUpperCase())}
            placeholder="e.g. 7K4PXR"
            autoFocus
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono tracking-widest mb-4"
          />
          <button
            type="submit"
            disabled={!codeInput.trim()}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
          >
            Continue
          </button>
        </form>
      </div>
    )
  }

  if (loading || authLoading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }

  if (error && !preview) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-md text-center">
          <h1 className="text-xl font-bold text-slate-900 mb-2">This link doesn't work</h1>
          <p className="text-sm text-slate-500">{error}</p>
        </div>
      </div>
    )
  }

  const redirectPath = `/join/${token}`

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-md text-center">
        <h1 className="text-xl font-bold text-slate-900 mb-1">You're invited</h1>
        <p className="text-sm text-slate-600 mb-1">
          Join <span className="font-semibold">{preview.workspace_name}</span>
        </p>
        <p className="text-xs text-slate-500 mb-6">
          {WORKSPACE_TYPE_LABELS[preview.workspace_type]} · as {ROLE_LABELS[preview.role] || preview.role} ·{' '}
          {preview.label}
        </p>

        {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

        {user ? (
          <button
            onClick={handleJoin}
            disabled={joining}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {joining ? 'Joining…' : `Accept and join as ${ROLE_LABELS[preview.role] || preview.role}`}
          </button>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-slate-500 mb-2">Log in or create an account to accept this invite.</p>
            <button
              onClick={() => navigate(`/login?redirect=${encodeURIComponent(redirectPath)}`)}
              className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium"
            >
              Log in
            </button>
            <button
              onClick={() => navigate(`/signup?redirect=${encodeURIComponent(redirectPath)}`)}
              className="w-full border border-slate-300 text-slate-700 hover:bg-slate-50 py-2 rounded-lg font-medium"
            >
              Sign up
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
