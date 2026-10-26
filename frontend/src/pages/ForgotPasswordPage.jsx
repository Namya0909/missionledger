import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth.jsx'
import { friendlyError } from '../lib/friendlyError'

export default function ForgotPasswordPage() {
  const { completeLogin } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [question, setQuestion] = useState(null) // {key, question, options}
  const [answer, setAnswer] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleStart(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const data = await api.recoverStart({ email })
      setQuestion(data.question)
      setAnswer('')
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleComplete(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const data = await api.recoverComplete({
        email,
        question_key: question.key,
        answer,
        new_password: newPassword,
      })
      completeLogin(data)
      navigate('/')
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center gap-6 px-4 py-10">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-700 text-white">
        <Wallet size={22} strokeWidth={1.75} />
      </div>

      {question === null ? (
        <form onSubmit={handleStart} className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-sm">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Forgot your password?</h1>
          <p className="text-sm text-slate-500 mb-6">
            Enter your email and we'll ask your security question so you can set a new one.
          </p>
          {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

          <label className="block text-sm text-slate-600 mb-5">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {submitting ? 'Checking…' : 'Continue'}
          </button>

          <p className="text-sm text-slate-500 mt-4 text-center">
            <Link to="/login" className="text-emerald-700 font-medium">
              Back to log in
            </Link>
          </p>
        </form>
      ) : (
        <form onSubmit={handleComplete} className="bg-white border border-slate-200 rounded-xl card-shadow p-8 w-full max-w-sm">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Reset your password</h1>
          <p className="text-sm text-slate-500 mb-6">Answer your security question and choose a new password.</p>
          {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

          <label className="block text-sm text-slate-600 mb-3">
            {question.question}
            <select
              required
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="" disabled>
                Pick your answer…
              </option>
              {question.options.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm text-slate-600 mb-5">
            New password
            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {submitting ? 'Resetting…' : 'Reset password'}
          </button>

          <p className="text-sm text-slate-500 mt-4 text-center">
            <button type="button" onClick={() => setQuestion(null)} className="text-emerald-700 font-medium hover:underline">
              Start over
            </button>
          </p>
        </form>
      )}
    </div>
  )
}
