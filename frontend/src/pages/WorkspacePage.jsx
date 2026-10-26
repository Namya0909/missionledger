import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeftRight,
  CheckSquare,
  Cpu,
  FileBarChart,
  History,
  Home,
  PiggyBank,
  Receipt,
  Search,
  ShieldCheck,
  Upload,
  Users,
  Zap,
} from 'lucide-react'
import ApprovalsPanel from '../components/ApprovalsPanel'
import AuditLogPanel from '../components/AuditLogPanel'
import ChatWidget from '../components/ChatWidget'
import CoupleToggle from '../components/CoupleToggle'
import CreatePotForm from '../components/CreatePotForm'
import CreateTransactionForm from '../components/CreateTransactionForm'
import EmptyState from '../components/EmptyState'
import IntakePanel from '../components/IntakePanel'
import MembersPanel from '../components/MembersPanel'
import NeedsAttention from '../components/NeedsAttention'
import PotCard from '../components/PotCard'
import RecurringChargesPanel from '../components/RecurringChargesPanel'
import ReportsPanel from '../components/ReportsPanel'
import SecurityLogPanel from '../components/SecurityLogPanel'
import SettleUpPanel from '../components/SettleUpPanel'
import SpendingChart from '../components/SpendingChart'
import TaxPackPanel from '../components/TaxPackPanel'
import TransactionCard from '../components/TransactionCard'
import TransactionRow from '../components/TransactionRow'
import WelcomeTour from '../components/WelcomeTour'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth.jsx'
import { friendlyError } from '../lib/friendlyError'
import { hasCapability } from '../lib/permissions'
import { formatUSD, formatUSDate } from '../lib/format'

export default function WorkspacePage() {
  const { id } = useParams()
  const { user } = useAuth()
  const workspaceId = Number(id)

  const [workspace, setWorkspace] = useState(null)
  const [pots, setPots] = useState([])
  const [transactions, setTransactions] = useState([])
  const [members, setMembers] = useState([])
  const [aiUsage, setAIUsage] = useState([])
  const [attention, setAttention] = useState([])
  const [attentionLoading, setAttentionLoading] = useState(true)
  const [approvalCount, setApprovalCount] = useState(0)
  const [tab, setTab] = useState('Home')
  const [showPotForm, setShowPotForm] = useState(false)
  const [showTxnForm, setShowTxnForm] = useState(false)
  const [editingTransaction, setEditingTransaction] = useState(null)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [filterPot, setFilterPot] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterPerson, setFilterPerson] = useState('')
  const [showTour, setShowTour] = useState(false)

  const isGroup = workspace?.type === 'group'
  const myMembership = members.find((m) => m.user.id === user?.id)
  const canManagePots = workspace && myMembership && hasCapability(workspace.type, myMembership.role, 'manage_pots')
  const canCreateTxn = workspace && myMembership && hasCapability(workspace.type, myMembership.role, 'create_transaction')
  const canManageMembers = workspace && myMembership && hasCapability(workspace.type, myMembership.role, 'manage_members')

  const TABS = [
    'Home',
    'Transactions',
    'Approvals',
    ...(isGroup ? ['Settle Up'] : []),
    // Intake needs create_transaction (statement/receipt) or manage_pots (grant
    // PDF) — gating the whole tab behind manage_pots alone would hide the
    // statement/receipt sections from anyone who can add expenses but doesn't
    // manage pots (e.g. a nonprofit volunteer). Reports and the Security Log
    // stay restricted to manage_pots specifically — those are workspace-wide
    // financial/security views, a different trust tier.
    ...(canCreateTxn || canManagePots ? ['Intake'] : []),
    ...(canManagePots ? ['Reports', 'Security Log'] : []),
    'Members',
    'Activity',
    'AI Usage',
  ]

  const TAB_ICONS = {
    Home,
    Transactions: Receipt,
    Approvals: CheckSquare,
    'Settle Up': ArrowLeftRight,
    Intake: Upload,
    Reports: FileBarChart,
    'Security Log': ShieldCheck,
    Members: Users,
    Activity: History,
    'AI Usage': Cpu,
  }

  function loadCore() {
    // getWorkspace is the one call whose failure means the whole page can't
    // render at all (e.g. a workspace you're not a member of) — without this
    // catch, a rejected promise left `workspace` null forever and the page
    // just sat on "Loading…" with no explanation.
    api.getWorkspace(workspaceId).then(setWorkspace).catch((err) => setLoadError(err.message))
    api.listPots(workspaceId).then(setPots)
    api.listMembers(workspaceId).then(setMembers)
    api.listAIUsage(workspaceId).then(setAIUsage)
    api.countMyApprovals(workspaceId).then(setApprovalCount)
  }

  function loadTransactions() {
    api
      .listTransactions(workspaceId, {
        pot_id: filterPot || undefined,
        status_filter: filterStatus || undefined,
        created_by_user_id: filterPerson || undefined,
      })
      .then(setTransactions)
  }

  function loadAttention() {
    setAttentionLoading(true)
    api
      .getAttention(workspaceId)
      .then(setAttention)
      .finally(() => setAttentionLoading(false))
  }

  useEffect(loadCore, [workspaceId])
  useEffect(loadTransactions, [workspaceId, filterPot, filterStatus, filterPerson])
  useEffect(loadAttention, [workspaceId])

  // First-ever visit tour — client-side only, keyed per user so it shows once
  // and never again on this browser, even across different workspaces.
  useEffect(() => {
    if (!user || pots.length === 0) return
    if (!localStorage.getItem(`missionledger_tour_seen_${user.id}`)) setShowTour(true)
  }, [user, pots.length])

  function dismissTour() {
    if (user) localStorage.setItem(`missionledger_tour_seen_${user.id}`, '1')
    setShowTour(false)
  }

  function refreshAfterChange() {
    loadCore()
    loadTransactions()
    loadAttention()
  }

  async function handleCreatePot(payload) {
    await api.createPot(workspaceId, payload)
    setShowPotForm(false)
    refreshAfterChange()
  }

  async function handleCreateTransaction(payload) {
    setError('')
    try {
      await api.createTransaction(workspaceId, payload)
      setShowTxnForm(false)
      refreshAfterChange()
    } catch (err) {
      setError(friendlyError(err))
      throw err
    }
  }

  async function handleUpdateTransaction(payload) {
    setError('')
    try {
      await api.updateTransaction(workspaceId, editingTransaction.id, payload)
      setEditingTransaction(null)
      refreshAfterChange()
    } catch (err) {
      setError(friendlyError(err))
      throw err
    }
  }

  async function handleDeleteTransaction(transactionId) {
    setError('')
    try {
      await api.deleteTransaction(workspaceId, transactionId)
      refreshAfterChange()
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  async function handleDecide(transactionId, approve, reason) {
    await api.decideTransaction(workspaceId, transactionId, approve, reason)
    refreshAfterChange()
  }

  function startEditing(transaction) {
    setShowTxnForm(false)
    setEditingTransaction(transaction)
  }

  const recentTransactions = transactions.slice(0, 6)

  if (loadError) {
    return (
      <div className="p-8 text-center max-w-md mx-auto">
        <p className="text-rose-600 font-medium mb-2">Couldn't open this workspace</p>
        <p className="text-sm text-slate-500 mb-4">{loadError}</p>
        <Link to="/" className="text-emerald-700 text-sm hover:underline">
          ← Back to your workspaces
        </Link>
      </div>
    )
  }
  if (!workspace) return <div className="p-8 text-center text-slate-500">Loading…</div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 sm:py-8">
      <Link to="/" className="text-sm text-emerald-700">
        ← All workspaces
      </Link>
      <div className="flex items-center gap-2 mt-1 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{workspace.name}</h1>
        {isGroup && workspace.member_count === 2 && (
          <CoupleToggle workspaceId={workspaceId} isCouple={workspace.is_couple} onChanged={loadCore} />
        )}
      </div>

      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 mb-6 overflow-x-auto">
        {TABS.map((t) => {
          const TabIcon = TAB_ICONS[t]
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap flex items-center gap-1.5 transition-colors ${
                tab === t ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {TabIcon && <TabIcon size={14} strokeWidth={2} />}
              {t}
              {t === 'Approvals' && approvalCount > 0 && (
                <span className="bg-rose-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                  {approvalCount}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {error && <p className="text-sm text-rose-600 mb-4">{error}</p>}

      {tab === 'Home' && (
        <div className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900">Pots</h2>
              {canManagePots && (
                <button
                  onClick={() => setShowPotForm((s) => !s)}
                  className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium"
                >
                  {showPotForm ? 'Cancel' : '+ New Pot'}
                </button>
              )}
            </div>
            {showPotForm && (
              <div className="mb-3">
                <CreatePotForm
                  onCreate={handleCreatePot}
                  onCancel={() => setShowPotForm(false)}
                  isGroup={isGroup}
                  members={members}
                />
              </div>
            )}
            <div className="grid sm:grid-cols-2 gap-4">
              {pots.map((pot) => (
                <PotCard
                  key={pot.id}
                  pot={pot}
                  workspaceId={workspaceId}
                  members={members}
                  canManagePots={canManagePots}
                  onChanged={refreshAfterChange}
                />
              ))}
            </div>
            {pots.length === 0 && (
              <EmptyState
                icon={PiggyBank}
                message={
                  canManagePots
                    ? 'No pots yet — use "+ New Pot" above to create your first one.'
                    : 'No pots yet — ask an admin to create one.'
                }
              />
            )}
          </div>

          <div>
            <h2 className="font-semibold text-slate-900 mb-3">Needs Attention</h2>
            <NeedsAttention items={attention} loading={attentionLoading} />
          </div>

          <div className="grid sm:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
              <h2 className="font-semibold text-slate-900 mb-3">Spending by Category</h2>
              <SpendingChart transactions={transactions} />
            </div>
            <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
              <h2 className="font-semibold text-slate-900 mb-3">Recent Transactions</h2>
              <ul className="divide-y divide-slate-100">
                {recentTransactions.map((t) => (
                  <li key={t.id} className="py-2 flex items-center justify-between text-sm">
                    <div>
                      <p className="font-medium text-slate-900">{t.merchant}</p>
                      <p className="text-xs text-slate-500">
                        {formatUSDate(t.date)} · {t.pot_name} · {t.created_by_name}
                      </p>
                    </div>
                    <span className="font-semibold text-slate-900 tabular-nums">{formatUSD(t.amount)}</span>
                  </li>
                ))}
                {recentTransactions.length === 0 && (
                  <EmptyState
                    icon={Receipt}
                    message="No transactions yet."
                    action={
                      (canCreateTxn || canManagePots) && (
                        <button
                          onClick={() => setTab('Intake')}
                          className="text-sm text-emerald-700 hover:underline font-medium"
                        >
                          Upload your first bank statement →
                        </button>
                      )
                    }
                  />
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {tab === 'Transactions' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 justify-between">
            <div className="flex flex-wrap gap-2">
              <select
                value={filterPot}
                onChange={(e) => setFilterPot(e.target.value)}
                className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
              >
                <option value="">All pots</option>
                {pots.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
              >
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <select
                value={filterPerson}
                onChange={(e) => setFilterPerson(e.target.value)}
                className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
              >
                <option value="">Everyone</option>
                {members.map((m) => (
                  <option key={m.user.id} value={m.user.id}>
                    {m.user.name}
                  </option>
                ))}
              </select>
            </div>
            {canCreateTxn && (
              <button
                onClick={() => setShowTxnForm((s) => !s)}
                disabled={!pots.length}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {showTxnForm ? 'Cancel' : '+ Add Expense'}
              </button>
            )}
          </div>
          {editingTransaction ? (
            <CreateTransactionForm
              pots={pots}
              transaction={editingTransaction}
              onSave={handleUpdateTransaction}
              onCancel={() => setEditingTransaction(null)}
            />
          ) : (
            showTxnForm && (
              <CreateTransactionForm
                pots={pots}
                onCreate={handleCreateTransaction}
                onCancel={() => setShowTxnForm(false)}
              />
            )
          )}
          {/* Cards on small screens, a full table from sm: up */}
          <div className="sm:hidden space-y-2">
            {transactions.map((txn) => (
              <TransactionCard
                key={txn.id}
                transaction={txn}
                workspaceId={workspaceId}
                onDecide={handleDecide}
                onChanged={refreshAfterChange}
                onEdit={startEditing}
                onDelete={handleDeleteTransaction}
              />
            ))}
            {transactions.length === 0 && <EmptyState icon={Search} message="No transactions match these filters — try clearing one." />}
          </div>

          <div className="hidden sm:block bg-white border border-slate-200 rounded-xl card-shadow p-4 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-slate-400 uppercase">
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Merchant</th>
                  <th className="py-2 pr-4 font-medium">Pot</th>
                  <th className="py-2 pr-4 font-medium">Category</th>
                  <th className="py-2 pr-4 font-medium">Added by</th>
                  <th className="py-2 pr-4 font-medium text-right">Amount</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <TransactionRow
                    key={txn.id}
                    transaction={txn}
                    workspaceId={workspaceId}
                    onDecide={handleDecide}
                    onChanged={refreshAfterChange}
                    onEdit={startEditing}
                    onDelete={handleDeleteTransaction}
                  />
                ))}
              </tbody>
            </table>
            {transactions.length === 0 && <EmptyState icon={Search} message="No transactions match these filters — try clearing one." />}
          </div>

          {canCreateTxn && <RecurringChargesPanel workspaceId={workspaceId} pots={pots} canCreate={canCreateTxn} />}
        </div>
      )}

      {tab === 'Approvals' && (
        <ApprovalsPanel workspaceId={workspaceId} onChanged={refreshAfterChange} />
      )}

      {tab === 'Settle Up' && (
        <SettleUpPanel workspaceId={workspaceId} members={members} currentUserId={user.id} />
      )}

      {tab === 'Intake' && <IntakePanel workspaceId={workspaceId} onChanged={refreshAfterChange} />}

      {tab === 'Reports' && (
        <div className="space-y-4">
          <ReportsPanel workspaceId={workspaceId} />
          <TaxPackPanel
            workspaceId={workspaceId}
            workspace={workspace}
            canManageMembers={canManageMembers}
            onChanged={refreshAfterChange}
          />
        </div>
      )}

      {tab === 'Security Log' && <SecurityLogPanel workspaceId={workspaceId} />}

      {tab === 'Members' && (
        <MembersPanel
          workspaceId={workspaceId}
          workspaceType={workspace.type}
          workspace={workspace}
          members={members}
          canManageMembers={canManageMembers}
          onChanged={refreshAfterChange}
        />
      )}

      {tab === 'Activity' && <AuditLogPanel workspaceId={workspaceId} />}

      {tab === 'AI Usage' && (
        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
          <AIUsagePanel usage={aiUsage} />
        </div>
      )}

      <ChatWidget workspaceId={workspaceId} />
      {showTour && <WelcomeTour onDone={dismissTour} />}
    </div>
  )
}

function AIUsagePanel({ usage }) {
  if (!usage.length) return <EmptyState icon={Zap} message="No AI calls logged yet for this workspace." />
  const totalCost = usage.reduce((sum, u) => sum + u.cost_usd, 0)
  const totalTokens = usage.reduce((sum, u) => sum + u.input_tokens + u.output_tokens, 0)
  const byPurpose = {}
  for (const u of usage) byPurpose[u.purpose] = (byPurpose[u.purpose] || 0) + 1

  return (
    <div>
      <div className="flex flex-wrap gap-6 mb-4">
        <div>
          <p className="text-xs text-slate-500">Total AI calls</p>
          <p className="text-xl font-bold text-slate-900">{usage.length}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total tokens</p>
          <p className="text-xl font-bold text-slate-900">{totalTokens.toLocaleString('en-US')}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total cost</p>
          <p className="text-xl font-bold text-slate-900">${totalCost.toFixed(4)}</p>
        </div>
      </div>
      <div className="text-sm text-slate-600 space-y-1">
        {Object.entries(byPurpose).map(([purpose, count]) => (
          <div key={purpose} className="flex justify-between border-b border-slate-100 py-1">
            <span className="capitalize">{purpose.replaceAll('_', ' ')}</span>
            <span>{count} calls</span>
          </div>
        ))}
      </div>
    </div>
  )
}
