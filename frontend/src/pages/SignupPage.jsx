import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Landmark, Store, Users, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth.jsx'
import { WORKSPACE_TYPE_BLURBS, WORKSPACE_TYPE_LABELS } from '../lib/permissions'

const TYPE_OPTIONS = [
  { type: 'group', icon: Users },
  { type: 'nonprofit', icon: Landmark },
  { type: 'business', icon: Store },
]

function SecurityQuestionSlot({ index, pool, selection, otherKeys, onChange }) {
  const available = pool.filter((q) => q.key === selection.questionKey || !otherKeys.includes(q.key))
  const chosen = pool.find((q) => q.key === selection.questionKey)

  return (
    <div className="mb-2">
      <select
        required
        value={selection.questionKey}
        onChange={(e) => onChange(index, { questionKey: e.target.value, answer: '' })}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-1.5"
      >
        <option value="" disabled>
          Security question {index + 1}…
        </option>
        {available.map((q) => (
          <option key={q.key} value={q.key}>
            {q.question}
          </option>
        ))}
      </select>
      {chosen && (
        <select
          required
          value={selection.answer}
          onChange={(e) => onChange(index, { ...selection, answer: e.target.value })}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="" disabled>
            Pick your answer…
          </option>
          {chosen.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}

export default function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirect = searchParams.get('redirect')

  const [step, setStep] = useState('choose') // 'choose' -> 'form'
  const [workspaceType, setWorkspaceType] = useState(null)
  const [wantsTaxPack, setWantsTaxPack] = useState(false)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [questionPool, setQuestionPool] = useState([])
  const [securitySelections, setSecuritySelections] = useState([
    { questionKey: '', answer: '' },
    { questionKey: '', answer: '' },
    { questionKey: '', answer: '' },
  ])

  useEffect(() => {
    api.getSecurityQuestions().then(setQuestionPool).catch(() => setQuestionPool([]))
  }, [])

  function updateSelection(index, next) {
    setSecuritySelections((prev) => prev.map((s, i) => (i === index ? next : s)))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (securitySelections.some((s) => !s.questionKey || !s.answer)) {
      setError('Please choose a question and answer for all 3 security questions.')
      return
    }
    setSubmitting(true)
    try {
      const securityAnswers = securitySelections.map((s) => ({ question_key: s.questionKey, answer: s.answer }))
      await signup(name, email, password, securityAnswers)
      navigate(redirect || '/get-started', { state: { workspaceType, wantsTaxPack } })
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'choose') {
    return (
      <div className="min-h-[80vh] flex flex-col items-center justify-center px-4 py-10">
        <div className="w-full max-w-2xl text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-emerald-700 text-white mb-4">
            <Wallet size={28} strokeWidth={1.75} />
          </div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Welcome to MissionLedger</h1>
          <p className="text-slate-500 max-w-lg mx-auto">
            Track shared money with AI-powered expense reviews, rule checks, and one-button
            reports. Start by telling us who this is for.
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 w-full max-w-2xl">
          {TYPE_OPTIONS.map(({ type, icon: Icon }) => (
            <button
              key={type}
              onClick={() => {
                setWorkspaceType(type)
                setStep('form')
              }}
              className="text-left bg-white border border-slate-200 hover:border-emerald-400 rounded-xl card-shadow p-5 transition hover:-translate-y-0.5"
            >
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-50 text-emerald-700 mb-3">
                <Icon size={20} strokeWidth={1.75} />
              </div>
              <p className="font-semibold text-slate-900 mb-1">{WORKSPACE_TYPE_LABELS[type]}</p>
              <p className="text-xs text-slate-500">{WORKSPACE_TYPE_BLURBS[type]}</p>
            </button>
          ))}
        </div>

        <button
          onClick={() => {
            setWorkspaceType(null)
            setStep('form')
          }}
          className="text-sm text-slate-400 hover:text-slate-600 mt-6"
        >
          Skip — I'll decide later
        </button>

        <p className="text-sm text-slate-500 mt-8">
          Already have an account?{' '}
          <Link to={redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'} className="text-emerald-700 font-medium">
            Log in
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center px-4 gap-4">
      <div className="w-full max-w-sm">
        {workspaceType && (
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl px-3 py-2 mb-3">
            <span>
              Setting up: <span className="font-semibold">{WORKSPACE_TYPE_LABELS[workspaceType]}</span>
            </span>
            <button
              onClick={() => setStep('choose')}
              className="inline-flex items-center gap-1 hover:underline font-medium"
            >
              <ArrowLeft size={12} /> change
            </button>
          </div>
        )}

        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-xl p-3 text-center mb-3">
          Beta for a class project. Please use the sample files or made-up numbers, not real bank
          statements —{' '}
          <a href="/samples/boa_statement_sample.csv" download className="underline font-medium">
            statement
          </a>
          {', '}
          <a href="/samples/receipt_sample.jpg" download className="underline font-medium">
            receipt
          </a>
          {', '}
          <a href="/samples/grant_agreement_sample.pdf" download className="underline font-medium">
            grant PDF
          </a>
          .
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl card-shadow p-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Create an account</h1>
          <p className="text-sm text-slate-500 mb-6">Get started with MissionLedger</p>
          {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

          <label className="block text-sm text-slate-600 mb-3">
            Name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm text-slate-600 mb-3">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm text-slate-600 mb-4">
            Password
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>

          <div className="mb-4">
            <p className="text-sm text-slate-600 mb-1.5">
              Security questions <span className="text-xs text-slate-400">(asked again at login, along with your password)</span>
            </p>
            {[0, 1, 2].map((i) => (
              <SecurityQuestionSlot
                key={i}
                index={i}
                pool={questionPool}
                selection={securitySelections[i]}
                otherKeys={securitySelections.filter((_, j) => j !== i).map((s) => s.questionKey).filter(Boolean)}
                onChange={updateSelection}
              />
            ))}
          </div>

          <label className="flex items-start gap-2 text-xs text-slate-600 mb-5 bg-slate-50 border border-slate-200 rounded-lg p-3">
            <input
              type="checkbox"
              checked={wantsTaxPack}
              onChange={(e) => setWantsTaxPack(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium text-slate-800">Also prepare tax paperwork for this workspace?</span>
              <br />
              Tax Prep Pack — optional, organizes documents for a CPA, TurboTax, or treasurer; it
              never files or advises. You can turn this on or off anytime.
            </span>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {submitting ? 'Creating account…' : 'Sign up'}
          </button>

          <p className="text-sm text-slate-500 mt-4 text-center">
            Already have an account?{' '}
            <Link
              to={redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'}
              className="text-emerald-700 font-medium"
            >
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
