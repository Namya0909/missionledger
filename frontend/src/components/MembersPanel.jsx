import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import { formatUSD } from '../lib/format'
import { ROLE_LABELS, rolesForWorkspaceType } from '../lib/permissions'

function MemberRow({ workspaceId, member, canManage, roles, onChanged }) {
  const [confirmingRemove, setConfirmingRemove] = useState(false)
  const [editingIncome, setEditingIncome] = useState(false)
  const [income, setIncome] = useState(member.monthly_income ?? '')
  const [error, setError] = useState('')

  async function changeRole(role) {
    setError('')
    try {
      await api.updateMemberRole(workspaceId, member.id, role)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  async function remove() {
    setError('')
    try {
      await api.removeMember(workspaceId, member.id)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
      setConfirmingRemove(false)
    }
  }

  async function saveIncome() {
    setError('')
    try {
      await api.setIncome(workspaceId, member.id, income === '' ? null : Number(income))
      setEditingIncome(false)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  return (
    <li className="py-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="font-medium text-slate-900">{member.user.name}</p>
          <p className="text-xs text-slate-500">{member.user.email}</p>
        </div>

        <div className="flex items-center gap-2">
          {canManage ? (
            <select
              value={member.role}
              onChange={(e) => changeRole(e.target.value)}
              className="text-xs font-medium rounded-lg border border-slate-300 px-2 py-1 bg-white"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r] || r}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
              {ROLE_LABELS[member.role] || member.role}
            </span>
          )}

          {canManage && !confirmingRemove && (
            <button onClick={() => setConfirmingRemove(true)} className="text-xs text-rose-600 hover:underline">
              Remove
            </button>
          )}
          {confirmingRemove && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Remove?</span>
              <button onClick={remove} className="bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded-lg">
                Yes
              </button>
              <button onClick={() => setConfirmingRemove(false)} className="text-slate-500 px-1">
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mt-1 text-xs text-slate-500">
        {editingIncome ? (
          <span className="inline-flex items-center gap-1">
            Income $
            <input
              type="number"
              autoFocus
              value={income}
              onChange={(e) => setIncome(e.target.value)}
              className="w-20 rounded border border-slate-300 px-1 py-0.5 text-xs"
            />
            /mo
            <button onClick={saveIncome} className="text-emerald-700 hover:underline font-medium ml-1">
              Save
            </button>
            <button onClick={() => setEditingIncome(false)} className="text-slate-500">
              Cancel
            </button>
          </span>
        ) : (
          <span>
            {member.monthly_income != null ? `Income ${formatUSD(member.monthly_income)}/mo` : 'No income on file'}
            {canManage && (
              <button onClick={() => setEditingIncome(true)} className="text-emerald-700 hover:underline font-medium ml-2">
                Edit
              </button>
            )}
          </span>
        )}
      </div>

      {error && <p className="text-xs text-rose-600 mt-1">{error}</p>}
    </li>
  )
}

function AddMemberForm({ workspaceId, roles, onChanged }) {
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState(roles[0] || '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await api.addMember(workspaceId, { email, role })
      setEmail('')
      setOpen(false)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-sm text-emerald-700 hover:underline font-medium mb-3"
      >
        + Invite member
      </button>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3 space-y-2">
      <p className="text-xs text-slate-500">
        They need an account already — invite them to sign up first if they don't have one.
      </p>
      <div className="flex gap-2 flex-wrap">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email address"
          className="flex-1 min-w-[180px] text-sm rounded-lg border border-slate-300 px-3 py-1.5"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        >
          {roles.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r] || r}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {submitting ? 'Adding…' : 'Add'}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-sm text-slate-500 hover:underline">
          Cancel
        </button>
      </div>
    </form>
  )
}

function InviteCodesPanel({ workspaceId, roles }) {
  const [codes, setCodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [role, setRole] = useState(roles[0] || '')
  const [generating, setGenerating] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      setCodes(await api.listInviteCodes(workspaceId))
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId])

  async function generate() {
    setGenerating(true)
    setError('')
    try {
      await api.createInviteCode(workspaceId, role)
      await load()
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setGenerating(false)
    }
  }

  function copy(code, id) {
    navigator.clipboard.writeText(code).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 1500)
    })
  }

  async function deactivate(id) {
    setError('')
    try {
      await api.deactivateInviteCode(workspaceId, id)
      await load()
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  if (loading) return null

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
      <p className="text-sm font-medium text-slate-800 mb-2">Invite codes</p>
      <p className="text-xs text-slate-500 mb-3">
        Generate a short code and share it — anyone with an account can use it to join with the role you pick.
      </p>

      <div className="flex gap-2 flex-wrap mb-3">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        >
          {roles.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r] || r}
            </option>
          ))}
        </select>
        <button
          onClick={generate}
          disabled={generating}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {generating ? 'Generating…' : 'Generate a join code'}
        </button>
      </div>

      {error && <p className="text-xs text-rose-600 mb-2">{error}</p>}

      {codes.length > 0 && (
        <ul className="space-y-2">
          {codes.map((c) => (
            <li key={c.id} className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg p-2">
              <span className="text-xs font-medium text-slate-600 w-28 shrink-0">{ROLE_LABELS[c.role] || c.role}</span>
              <span className="flex-1 text-base font-mono font-semibold tracking-widest text-slate-700">{c.token}</span>
              <button onClick={() => copy(c.token, c.id)} className="text-xs font-medium text-emerald-700 hover:underline shrink-0">
                {copiedId === c.id ? 'Copied!' : 'Copy'}
              </button>
              <button onClick={() => deactivate(c.id)} className="text-xs text-rose-600 hover:underline shrink-0">
                Deactivate
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TaxPackToggle({ workspaceId, enabled, canManage, onChanged }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function toggle() {
    setSubmitting(true)
    setError('')
    try {
      await api.setTaxPackEnabled(workspaceId, !enabled)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
      <div>
        <p className="text-sm font-medium text-slate-800">Tax Prep Pack</p>
        <p className="text-xs text-slate-500">Organizes paperwork for tax time — never files, never advises.</p>
        {error && <p className="text-xs text-rose-600 mt-1">{error}</p>}
      </div>
      {canManage ? (
        <button
          onClick={toggle}
          disabled={submitting}
          className={`text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 ${
            enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
          }`}
        >
          {submitting ? 'Saving…' : enabled ? 'On — turn off' : 'Off — turn on'}
        </button>
      ) : (
        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
          {enabled ? 'On' : 'Off'}
        </span>
      )}
    </div>
  )
}

export default function MembersPanel({ workspaceId, workspaceType, workspace, members, canManageMembers, onChanged }) {
  const roles = rolesForWorkspaceType(workspaceType)

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
      {workspace && (
        <TaxPackToggle
          workspaceId={workspaceId}
          enabled={workspace.tax_pack_enabled}
          canManage={canManageMembers}
          onChanged={onChanged}
        />
      )}
      {canManageMembers && <InviteCodesPanel workspaceId={workspaceId} roles={roles} />}
      {canManageMembers && <AddMemberForm workspaceId={workspaceId} roles={roles} onChanged={onChanged} />}
      <ul className="divide-y divide-slate-100">
        {members.map((m) => (
          <MemberRow
            key={m.id}
            workspaceId={workspaceId}
            member={m}
            canManage={canManageMembers}
            roles={roles}
            onChanged={onChanged}
          />
        ))}
      </ul>
    </div>
  )
}
