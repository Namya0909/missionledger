import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth.jsx'

const DEMO_ACCOUNTS = [
  {
    group: 'Oak Street House — Group (4 roommates)',
    accounts: [
      { label: 'Maya (admin)', email: 'maya@demo.org' },
      { label: 'Josh (member)', email: 'josh@demo.org' },
      { label: 'Sam (member)', email: 'sam@demo.org' },
      { label: 'Lena (member)', email: 'lena@demo.org' },
    ],
  },
  {
    group: 'Elm Street Community Food Bank — Nonprofit',
    accounts: [
      { label: 'Priya (volunteer — adds expenses)', email: 'volunteer@demo.org' },
      { label: 'Omar (volunteer — adds expenses)', email: 'volunteer2@demo.org' },
      { label: 'Grace (volunteer — adds expenses)', email: 'volunteer3@demo.org' },
      { label: 'Marcus (treasurer — approves)', email: 'treasurer@demo.org' },
      { label: 'Dana (board — view only)', email: 'board@demo.org' },
    ],
  },
  {
    group: 'Corner Coffee Co. — Business',
    accounts: [
      { label: 'Theo (owner — approves)', email: 'owner@demo.org' },
      { label: 'Jordan (staff — adds expenses)', email: 'staff@demo.org' },
      { label: 'Riley (staff — adds expenses)', email: 'staff2@demo.org' },
      { label: 'Alicia (bookkeeper — view only)', email: 'bookkeeper@demo.org' },
    ],
  },
]

const DEMO_PASSWORD = 'demo1234'
// Matches seed.py's DEMO_SECURITY_ANSWERS — every demo account uses these, so the
// one-click buttons below can complete both login steps without showing the UI.
const DEMO_SECURITY_ANSWERS = { color: 'Blue', pet: 'Dog', food: 'Pizza' }

export default function LoginPage() {
  const { completeLogin } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirect = searchParams.get('redirect')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState('')

  // Step 2 state: once step 1 succeeds, these hold the account's own 3 questions
  // and the ticket that proves the password was already checked.
  const [loginTicket, setLoginTicket] = useState(null)
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})

  function resetToStep1() {
    setLoginTicket(null)
    setQuestions([])
    setAnswers({})
    setError('')
  }

  async function handleStep1(e) {
    e?.preventDefault()
    setError('')
    setSubmitting('form')
    try {
      const data = await api.loginStep1({ email, password })
      setQuestions(data.questions)
      setLoginTicket(data.login_ticket)
      setAnswers({})
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting('')
    }
  }

  async function handleStep2(e) {
    e.preventDefault()
    setError('')
    setSubmitting('form')
    try {
      const data = await api.loginStep2({
        login_ticket: loginTicket,
        answers: questions.map((q) => ({ question_key: q.key, answer: answers[q.key] })),
      })
      completeLogin(data)
      navigate(redirect || '/')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting('')
    }
  }

  // One-click demo login: runs both steps back-to-back with the known demo
  // security answers, so it stays genuinely one click even though login is 2 steps.
  async function doDemoLogin(demoEmail) {
    setError('')
    setSubmitting(demoEmail)
    try {
      const step1 = await api.loginStep1({ email: demoEmail, password: DEMO_PASSWORD })
      const demoAnswers = step1.questions.map((q) => ({ question_key: q.key, answer: DEMO_SECURITY_ANSWERS[q.key] }))
      const data = await api.loginStep2({ login_ticket: step1.login_ticket, answers: demoAnswers })
      completeLogin(data)
      navigate(redirect || '/')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting('')
    }
  }

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center gap-6 px-4 py-10">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-700 text-white">
        <Wallet size={22} strokeWidth={1.75} />
      </div>
      <div className="flex flex-col lg:flex-row items-center justify-center gap-6 w-full">
        {loginTicket ? (
          <form onSubmit={handleStep2} className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-sm">
            <h1 className="text-2xl font-bold text-slate-900 mb-1">Security questions</h1>
            <p className="text-sm text-slate-500 mb-6">Answer your 3 questions to finish logging in.</p>
            {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

            {questions.map((q) => (
              <label key={q.key} className="block text-sm text-slate-600 mb-3">
                {q.question}
                <select
                  required
                  value={answers[q.key] || ''}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.key]: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="" disabled>
                    Pick your answer…
                  </option>
                  {q.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </label>
            ))}

            <button
              type="submit"
              disabled={!!submitting}
              className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50 mt-2"
            >
              {submitting ? 'Logging in…' : 'Log in'}
            </button>
            <button type="button" onClick={resetToStep1} className="text-sm text-slate-500 hover:underline mt-3 w-full text-center">
              ← Start over
            </button>
          </form>
        ) : (
          <form onSubmit={handleStep1} className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-sm">
            <h1 className="text-2xl font-bold text-slate-900 mb-1">Welcome back</h1>
            <p className="text-sm text-slate-500 mb-6">Log in to MissionLedger</p>
            {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

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
            <label className="block text-sm text-slate-600 mb-5">
              Password
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>

            <button
              type="submit"
              disabled={!!submitting}
              className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
            >
              {submitting ? 'Checking…' : 'Continue'}
            </button>

            <p className="text-sm text-slate-500 mt-4 text-center">
              No account?{' '}
              <Link
                to={redirect ? `/signup?redirect=${encodeURIComponent(redirect)}` : '/signup'}
                className="text-emerald-700 font-medium"
              >
                Sign up
              </Link>
            </p>
          </form>
        )}

        <div className="bg-white border border-slate-200 rounded-xl card-shadow p-6 w-full max-w-sm">
          <h2 className="font-semibold text-slate-900 mb-1">Try a demo</h2>
          <p className="text-xs text-slate-500 mb-4">
            Every account below uses password <code className="bg-slate-100 px-1 rounded">{DEMO_PASSWORD}</code>.
            Click one to log straight in.
          </p>
          <div className="space-y-4">
            {DEMO_ACCOUNTS.map((group) => (
              <div key={group.group}>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                  {group.group}
                </p>
                <div className="space-y-1.5">
                  {group.accounts.map((acct) => (
                    <button
                      key={acct.email}
                      type="button"
                      disabled={!!submitting}
                      onClick={() => doDemoLogin(acct.email)}
                      className="w-full text-left text-sm bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 rounded-lg px-3 py-2 transition disabled:opacity-50"
                    >
                      {submitting === acct.email ? 'Logging in…' : acct.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
