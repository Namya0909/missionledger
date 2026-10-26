import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import useRotatingMessages from '../lib/useRotatingMessages'
import SetupInviteRow from '../components/SetupInviteRow'
import SetupPlanPotCard from '../components/SetupPlanPotCard'
import SetupSavingsCard from '../components/SetupSavingsCard'

const THINKING_MESSAGES = ['Thinking it through…', 'Checking your pots…', 'Double-checking the numbers…']

const EXAMPLES = [
  'My goal is to save money with my wife',
  "I'm treasurer of a small nonprofit with two grants",
  'I run a coffee shop and want to stay on top of sales tax and payroll',
]

const MAX_QUESTIONS = 4

// When signup already captured which kind of workspace this is, open straight into
// the chat with that stated — the AI's first real question is about specifics, not
// "what kind of workspace is this."
const OPENING_MESSAGE_BY_TYPE = {
  group: "I'm setting up a budgeting workspace for a group of friends or family sharing expenses.",
  nonprofit: "I'm setting up a budgeting workspace for a small nonprofit.",
  business: "I'm setting up a budgeting workspace for a small business.",
}

// A light heuristic: when the agent's question has an obvious default answer,
// pre-fill it so the user can just hit enter instead of retyping the obvious thing.
function smartDefaultFor(reply) {
  const lower = reply.toLowerCase()
  if (lower.includes('split')) return 'Equally'
  return ''
}

export default function GetStartedPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const presetType = location.state?.workspaceType || null
  const wantsTaxPack = !!location.state?.wantsTaxPack

  // phase: 'intro' -> 'chat' -> 'plan' -> 'created'
  const [phase, setPhase] = useState('intro')
  const [messages, setMessages] = useState([]) // {role, content}
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [declined, setDeclined] = useState(false)
  const [questionNumber, setQuestionNumber] = useState(0)
  const [lastRequest, setLastRequest] = useState(null) // {message, history}
  const thinkingMessage = useRotatingMessages(THINKING_MESSAGES, sending)

  // Plan review state
  const [plan, setPlan] = useState(null)
  const [includedInvites, setIncludedInvites] = useState(new Set())
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  // Group workspaces only: whether everyone gets equal (admin-level) access, or
  // just the person setting this up. Defaults to "just me" since that's always a
  // safe, fully-functional config — a group can never be left with no one able to
  // manage pots or invite more people.
  const [groupAllAdmins, setGroupAllAdmins] = useState(false)

  // Created state
  const [createdWorkspaceId, setCreatedWorkspaceId] = useState(null)
  const [inviteLinks, setInviteLinks] = useState([])
  const [copiedIndex, setCopiedIndex] = useState(null)

  async function runSetupCall(message, history, baseMessages) {
    try {
      const res = await api.setupMessage(message, history)
      setQuestionNumber(res.question_number)
      if (res.error) {
        setError(res.error)
        return
      }
      const withReply = [...baseMessages, { role: 'assistant', content: res.reply }]
      setMessages(withReply)
      if (res.declined) {
        setDeclined(true)
      } else if (res.done && res.plan) {
        setPlan(res.plan)
        setIncludedInvites(new Set(res.plan.invites.map((_, i) => i)))
        setPhase('plan')
      } else {
        setInput(smartDefaultFor(res.reply))
      }
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSending(false)
    }
  }

  async function send(message) {
    setError('')
    setSending(true)
    const historySnapshot = messages
    const nextMessages = [...messages, { role: 'user', content: message }]
    setMessages(nextMessages)
    setLastRequest({ message, history: historySnapshot })
    await runSetupCall(message, historySnapshot, nextMessages)
  }

  async function retryLast() {
    if (!lastRequest) return
    setError('')
    setSending(true)
    await runSetupCall(lastRequest.message, lastRequest.history, messages)
  }

  // Signup already captured the workspace type — skip the "what do you want help
  // with?" intro screen and open straight into the chat with that stated.
  useEffect(() => {
    if (presetType && OPENING_MESSAGE_BY_TYPE[presetType]) {
      setPhase('chat')
      send(OPENING_MESSAGE_BY_TYPE[presetType])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleStart(e) {
    e?.preventDefault()
    if (!input.trim()) return
    setPhase('chat')
    const text = input.trim()
    setInput('')
    send(text)
  }

  function handleReply(e) {
    e.preventDefault()
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    send(text)
  }

  function reset() {
    setPhase('intro')
    setMessages([])
    setDeclined(false)
    setQuestionNumber(0)
    setError('')
    setInput('')
    setLastRequest(null)
  }

  function updatePot(index, nextPot) {
    setPlan((p) => ({ ...p, pots: p.pots.map((pot, i) => (i === index ? nextPot : pot)) }))
  }

  function removePot(index) {
    setPlan((p) => ({ ...p, pots: p.pots.filter((_, i) => i !== index) }))
  }

  function toggleInvite(index, included) {
    setIncludedInvites((s) => {
      const next = new Set(s)
      if (included) next.add(index)
      else next.delete(index)
      return next
    })
  }

  function updateInviteLabel(index, label) {
    setPlan((p) => ({ ...p, invites: p.invites.map((inv, i) => (i === index ? { ...inv, label } : inv)) }))
  }

  function setGroupAdminMode(allAdmins) {
    setGroupAllAdmins(allAdmins)
    setPlan((p) => ({
      ...p,
      invites: p.invites.map((inv) => ({ ...inv, role: allAdmins ? 'admin' : 'member' })),
    }))
  }

  async function handleCreate() {
    setCreating(true)
    setCreateError('')
    try {
      const payload = {
        workspace_type: plan.workspace_type,
        suggested_name: plan.suggested_name,
        pots: plan.pots,
        invites: plan.invites.filter((_, i) => includedInvites.has(i)),
        tax_pack_enabled: wantsTaxPack,
        state: plan.state,
      }
      const res = await api.setupCreate(payload)
      setCreatedWorkspaceId(res.workspace_id)
      setInviteLinks(res.invite_links)
      setPhase('created')
    } catch (err) {
      setCreateError(friendlyError(err))
    } finally {
      setCreating(false)
    }
  }

  function copyLink(url, index) {
    navigator.clipboard.writeText(url).then(() => {
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 1500)
    })
  }

  // ---------------------------------------------------------------------
  // Intro
  // ---------------------------------------------------------------------
  if (phase === 'intro') {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-lg">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Let's get you set up</h1>
          <p className="text-sm text-slate-500 mb-5">What do you want help with?</p>

          <form onSubmit={handleStart} className="space-y-3">
            <textarea
              autoFocus
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. My goal is to save money with my wife"
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
            >
              Get started
            </button>
          </form>

          <p className="text-xs text-slate-500 mt-5 mb-2">Or try an example:</p>
          <div className="space-y-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => {
                  setPhase('chat')
                  send(ex)
                }}
                className="w-full text-left text-sm bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 rounded-lg px-3 py-2 transition"
              >
                "{ex}"
              </button>
            ))}
          </div>

          <p className="text-xs text-slate-400 mt-5 text-center">
            Just setting up for yourself?{' '}
            <button onClick={() => navigate('/')} className="text-emerald-700 hover:underline">
              Skip and create a workspace manually
            </button>
          </p>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------
  if (phase === 'chat') {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-6 w-full max-w-lg">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-bold text-slate-900">Setting things up</h1>
            {!declined && (
              <span className="text-xs text-slate-400">
                {questionNumber > 0 ? `Question ${questionNumber} of ${MAX_QUESTIONS}` : 'Getting started…'}
              </span>
            )}
          </div>

          <div className="space-y-3 mb-4 max-h-96 overflow-y-auto">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                  m.role === 'user' ? 'bg-emerald-700 text-white ml-auto' : 'bg-slate-100 text-slate-800'
                }`}
              >
                {m.content}
              </div>
            ))}
            {sending && <div className="text-xs text-slate-400 px-1">{thinkingMessage}</div>}
          </div>

          {error && (
            <div className="mb-3">
              <p className="text-sm text-rose-600 mb-1">{error}</p>
              <button onClick={retryLast} className="text-sm text-emerald-700 hover:underline">
                Try again
              </button>
            </div>
          )}

          {declined ? (
            <button onClick={reset} className="text-sm text-emerald-700 hover:underline">
              ← Try a different request
            </button>
          ) : (
            <form onSubmit={handleReply} className="flex gap-2">
              <input
                autoFocus
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your answer…"
                disabled={sending}
                className="flex-1 text-sm rounded-lg border border-slate-300 px-3 py-2"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                Send
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------
  // Plan review — nothing is saved until "Create my workspace"
  // ---------------------------------------------------------------------
  if (phase === 'plan' && plan) {
    const isGroup = plan.workspace_type === 'group'

    return (
      <div className="min-h-screen px-4 py-10">
        <div className="max-w-2xl mx-auto space-y-5">
          <div>
            <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-1">Your plan</p>
            <input
              value={plan.suggested_name}
              onChange={(e) => setPlan((p) => ({ ...p, suggested_name: e.target.value }))}
              className="text-2xl font-bold text-slate-900 w-full rounded-lg border border-transparent hover:border-slate-200 focus:border-slate-300 px-2 py-1 -ml-2"
            />
            <p className="text-sm text-slate-600 mt-1">{plan.summary}</p>
          </div>

          <SetupSavingsCard analysis={plan.savings_analysis} />

          {isGroup && plan.invites.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
              <h2 className="text-sm font-semibold text-slate-700 mb-2">Who manages this group?</h2>
              <p className="text-xs text-slate-500 mb-3">
                Someone needs to be able to set up pots and invite people — that's always you, since you're
                creating this workspace. You can also give everyone else the same access instead of just you.
              </p>
              <div className="space-y-2">
                <label className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="group-admin-mode"
                    checked={!groupAllAdmins}
                    onChange={() => setGroupAdminMode(false)}
                    className="mt-0.5"
                  />
                  Just me — everyone else can add expenses, but only I manage pots and invites
                </label>
                <label className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="group-admin-mode"
                    checked={groupAllAdmins}
                    onChange={() => setGroupAdminMode(true)}
                    className="mt-0.5"
                  />
                  Everyone equally — no single admin, everyone can manage pots and invites
                </label>
              </div>
            </div>
          )}

          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-2">Pots</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {plan.pots.map((pot, i) => (
                <SetupPlanPotCard
                  key={i}
                  pot={pot}
                  isGroup={isGroup}
                  onChange={(next) => updatePot(i, next)}
                  onRemove={() => removePot(i)}
                />
              ))}
            </div>
            {plan.pots.length === 0 && (
              <p className="text-sm text-slate-400">No pots in this plan — you can always add one later from the workspace.</p>
            )}
          </div>

          {plan.invites.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-slate-700 mb-2">Invite links to send</h2>
              <div className="space-y-2">
                {plan.invites.map((invite, i) => (
                  <SetupInviteRow
                    key={i}
                    invite={invite}
                    included={includedInvites.has(i)}
                    onToggleIncluded={(checked) => toggleInvite(i, checked)}
                    onChangeLabel={(label) => updateInviteLabel(i, label)}
                  />
                ))}
              </div>
            </div>
          )}

          {createError && <p className="text-sm text-rose-600">{createError}</p>}

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleCreate}
              disabled={creating || !plan.suggested_name.trim()}
              className="bg-emerald-700 hover:bg-emerald-800 text-white px-5 py-2.5 rounded-lg font-medium disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create my workspace'}
            </button>
            <button onClick={reset} className="text-sm text-slate-500 hover:underline">
              Start over
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------
  // Created — show invite links, then hand off to the workspace
  // ---------------------------------------------------------------------
  if (phase === 'created') {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-lg">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">You're all set</h1>
          <p className="text-sm text-slate-500 mb-5">Your workspace was created. Share these links to invite others.</p>

          {inviteLinks.length > 0 && (
            <div className="space-y-2 mb-6">
              {inviteLinks.map((link, i) => (
                <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <p className="text-sm font-medium text-slate-800">{link.label}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <input
                      readOnly
                      value={link.url}
                      className="flex-1 text-xs text-slate-500 bg-white border border-slate-200 rounded px-2 py-1"
                    />
                    <button
                      onClick={() => copyLink(link.url, i)}
                      className="text-xs font-medium text-emerald-700 hover:underline shrink-0"
                    >
                      {copiedIndex === i ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => navigate(`/workspaces/${createdWorkspaceId}`)}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium"
          >
            Go to your workspace
          </button>
        </div>
      </div>
    )
  }

  return null
}
