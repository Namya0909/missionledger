import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Home, Landmark, Store, Users } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import { api } from '../lib/api'
import { formatUSDate } from '../lib/format'
import { WORKSPACE_TYPE_ACCENT, WORKSPACE_TYPE_LABELS } from '../lib/permissions'

const WORKSPACE_TYPE_ICON = { group: Users, nonprofit: Landmark, business: Store }

export default function WorkspacesPage() {
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState('group')
  const [taxPackEnabled, setTaxPackEnabled] = useState(false)
  const [state, setState] = useState('')
  const [error, setError] = useState('')
  const [joinCode, setJoinCode] = useState('')

  function refresh() {
    setLoading(true)
    api
      .listWorkspaces()
      .then((list) => {
        // Know your workspace from your login: with exactly one, skip straight to it
        // instead of making every demo user pick from a list of one.
        if (list.length === 1) {
          navigate(`/workspaces/${list[0].id}`, { replace: true })
          return
        }
        setWorkspaces(list)
      })
      .finally(() => setLoading(false))
  }

  useEffect(refresh, [])

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    try {
      await api.createWorkspace({ name, type, tax_pack_enabled: taxPackEnabled, state: type === 'business' ? state || null : null })
      setName('')
      setTaxPackEnabled(false)
      setState('')
      setShowForm(false)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  function handleJoin(e) {
    e.preventDefault()
    const code = joinCode.trim()
    if (code) navigate(`/join/${encodeURIComponent(code)}`)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Your Workspaces</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          {showForm ? 'Cancel' : '+ New Workspace'}
        </button>
      </div>

      <form onSubmit={handleJoin} className="bg-white border border-slate-200 rounded-xl card-shadow p-4 mb-6 flex items-end gap-2 flex-wrap">
        <label className="block text-sm text-slate-600 flex-1 min-w-[160px]">
          Have a join code?
          <input
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            placeholder="e.g. 7K4PXR"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono tracking-widest"
          />
        </label>
        <button
          type="submit"
          disabled={!joinCode.trim()}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          Join
        </button>
      </form>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border border-slate-200 rounded-xl card-shadow p-5 mb-6 space-y-3">
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <label className="block text-sm text-slate-600">
            Name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Oak Street House, Yale Food Bank, Corner Coffee Co."
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm text-slate-600">
            Type
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="group">{WORKSPACE_TYPE_LABELS.group} (2-10 people sharing money)</option>
              <option value="nonprofit">{WORKSPACE_TYPE_LABELS.nonprofit}</option>
              <option value="business">{WORKSPACE_TYPE_LABELS.business}</option>
            </select>
          </label>
          {type === 'business' && (
            <label className="block text-sm text-slate-600">
              State (optional — for an accurate sales-tax estimate)
              <input
                value={state}
                onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))}
                placeholder="e.g. CT"
                className="mt-1 w-24 rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
          )}
          <label className="flex items-start gap-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
            <input type="checkbox" checked={taxPackEnabled} onChange={(e) => setTaxPackEnabled(e.target.checked)} className="mt-0.5" />
            <span>
              <span className="font-medium text-slate-800">Also prepare tax paperwork?</span> Tax Prep Pack — optional,
              organizes documents for a CPA/TurboTax/treasurer; never files or advises. Toggle anytime from Members.
            </span>
          </label>
          <button type="submit" className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-1.5 rounded-lg text-sm font-medium">
            Create
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : workspaces.length === 0 ? (
        <EmptyState icon={Home} message="No workspaces yet — create your first one above to get started." />
      ) : (
        <ul className="space-y-3">
          {workspaces.map((ws) => {
            const Icon = WORKSPACE_TYPE_ICON[ws.type]
            return (
              <li key={ws.id}>
                <Link
                  to={`/workspaces/${ws.id}`}
                  className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl card-shadow p-4 hover:shadow-md transition"
                >
                  <span className={`shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-xl ${WORKSPACE_TYPE_ACCENT[ws.type]}`}>
                    {Icon && <Icon size={18} strokeWidth={1.75} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between">
                      <h2 className="font-semibold text-slate-900 truncate">{ws.name}</h2>
                      <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ml-2 ${WORKSPACE_TYPE_ACCENT[ws.type]}`}>
                        {WORKSPACE_TYPE_LABELS[ws.type]}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">Created {formatUSDate(ws.created_at)}</p>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
