import { useState } from 'react'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import useRotatingMessages from '../lib/useRotatingMessages'

const GENERATING_MESSAGES = ['Pulling together the numbers…', 'Writing your summary…', 'Formatting the PDF…']

export default function ReportsPanel({ workspaceId }) {
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const generatingMessage = useRotatingMessages(GENERATING_MESSAGES, generating)

  async function handleGenerate() {
    setError('')
    setGenerating(true)
    try {
      const { blob, filename } = await api.generateReport(workspaceId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-6">
      <h3 className="font-semibold text-slate-900 mb-1">Generate a Report</h3>
      <p className="text-sm text-slate-500 mb-4">
        One PDF covering what's relevant to this workspace: grant-by-grant spending and a board
        summary for nonprofits, a friendly monthly money check-in for groups, or sales, costs,
        and top action items for a business — plus what's still waiting for approval, either way.
      </p>
      {error && (
        <p className="text-sm text-rose-600 mb-3">
          {error} <button onClick={handleGenerate} className="text-emerald-700 hover:underline font-medium">Try again</button>
        </p>
      )}
      <button
        onClick={handleGenerate}
        disabled={generating}
        className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
      >
        {generating ? generatingMessage : 'Generate report (PDF)'}
      </button>
    </div>
  )
}
