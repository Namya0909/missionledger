import { useEffect, useState } from 'react'
import { FileSpreadsheet } from 'lucide-react'
import { api } from '../lib/api'
import EmptyState from './EmptyState'
import { friendlyError } from '../lib/friendlyError'
import { formatUSD, formatUSDate } from '../lib/format'
import useRotatingMessages from '../lib/useRotatingMessages'

const GENERATING_MESSAGES = ['Pulling together the numbers…', 'Writing the explanations…', 'Formatting the PDF…']
const DISCLAIMER = 'Prepared to help you file. Not tax advice. Please review with a CPA or tax professional.'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function GroupPreview({ data }) {
  if (!data.buckets.length) {
    return <p className="text-sm text-slate-500">Nothing matched a possibly tax-relevant category yet this year.</p>
  }
  return (
    <div className="space-y-3">
      {data.buckets.map((b) => (
        <div key={b.label} className="border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-sm">
            <p className="font-medium text-slate-800">{b.label}</p>
            <p className="font-semibold text-slate-900">{formatUSD(b.total)}</p>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">possibly relevant — confirm with a tax professional</p>
        </div>
      ))}
      <p className="text-sm font-semibold text-slate-900 text-right">Total: {formatUSD(data.grand_total)}</p>
    </div>
  )
}

function NonprofitPreview({ data }) {
  return (
    <div className="space-y-3 text-sm">
      <p>
        Gross receipts <span className="font-semibold">{formatUSD(data.gross_receipts)}</span> · Total spending{' '}
        <span className="font-semibold">{formatUSD(data.total_spending)}</span> · Total assets{' '}
        <span className="font-semibold">{formatUSD(data.total_assets)}</span>
      </p>
      <div className="border border-slate-200 rounded-lg p-3">
        <p className="font-medium text-slate-800">
          Likely filing: <span className="text-emerald-700">{data.filing_recommendation}</span>
        </p>
        <p className="text-xs text-slate-500 mt-1">{data.filing_reason}</p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        {Object.entries(data.bucket_totals).map(([k, v]) => (
          <div key={k} className="border border-slate-200 rounded-lg p-2">
            <p className="text-slate-500">{k}</p>
            <p className="font-semibold text-slate-900">{formatUSD(v)}</p>
          </div>
        ))}
      </div>
      {data.donors.length > 0 && (
        <div>
          <p className="font-medium text-slate-800 mb-1">Donors needing a thank-you letter ($250+)</p>
          <ul className="space-y-1 text-xs text-slate-600">
            {data.donors.map((d, i) => (
              <li key={i}>
                {d.donor_name} — {formatUSD(d.amount)} on {formatUSDate(d.date)}
              </li>
            ))}
          </ul>
          <p className="text-xs text-slate-400 mt-1">
            Only transactions with a category containing "Donation" are picked up as donors.
          </p>
        </div>
      )}
    </div>
  )
}

function BusinessPreview({ data }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="border border-slate-200 rounded-lg p-3">
        <p className="font-medium text-slate-800">Sales Tax Worksheet</p>
        <p className="mt-1">
          Taxable sales <span className="font-semibold">{formatUSD(data.taxable_sales)}</span> · Rate{' '}
          <span className="font-semibold">{(data.sales_tax_rate * 100).toFixed(2)}%</span>
          {data.rate_is_estimate && <span className="text-xs text-amber-600"> (estimate — confirm your state's rate)</span>}
        </p>
        <p>
          Tax owed <span className="font-semibold">{formatUSD(data.tax_owed)}</span> · Already saved{' '}
          <span className="font-semibold">{formatUSD(data.already_saved)}</span>
        </p>
      </div>
      <p>
        Next estimated-tax due date: <span className="font-semibold">{formatUSDate(data.next_estimated_due_date)}</span>
      </p>
      <div>
        <p className="font-medium text-slate-800 mb-1">Contractors paid $600+ this year (review for a possible 1099-NEC)</p>
        {data.contractors.length === 0 ? (
          <p className="text-xs text-slate-500">No single vendor was paid $600 or more this year.</p>
        ) : (
          <ul className="space-y-1 text-xs text-slate-600">
            {data.contractors.map((c) => (
              <li key={c.merchant}>
                {c.merchant} — {formatUSD(c.total_paid)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default function TaxPackPanel({ workspaceId, workspace, canManageMembers, onChanged }) {
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [togglingOn, setTogglingOn] = useState(false)
  const [error, setError] = useState('')
  const generatingMessage = useRotatingMessages(GENERATING_MESSAGES, generating)

  useEffect(() => {
    if (!workspace.tax_pack_enabled) return
    setLoading(true)
    setError('')
    api
      .getTaxPack(workspaceId, year)
      .then(setData)
      .catch((err) => setError(friendlyError(err)))
      .finally(() => setLoading(false))
  }, [workspaceId, year, workspace.tax_pack_enabled])

  async function enableTaxPack() {
    setTogglingOn(true)
    try {
      await api.setTaxPackEnabled(workspaceId, true)
      onChanged()
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setTogglingOn(false)
    }
  }

  async function handleDownloadPdf() {
    setError('')
    setGenerating(true)
    try {
      const { blob, filename } = await api.generateTaxPackPdf(workspaceId, year)
      downloadBlob(blob, filename)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setGenerating(false)
    }
  }

  async function handleDownloadCsv() {
    setError('')
    try {
      const { blob, filename } = await api.getTaxPackCsv(workspaceId, year)
      downloadBlob(blob, filename)
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  if (!workspace.tax_pack_enabled) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-6">
        <EmptyState
          icon={FileSpreadsheet}
          message="The Tax Prep Pack isn't turned on for this workspace — it organizes paperwork for tax time (never files, never advises)."
          action={
            canManageMembers ? (
              <button
                onClick={enableTaxPack}
                disabled={togglingOn}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {togglingOn ? 'Turning on…' : 'Turn on Tax Prep Pack'}
              </button>
            ) : (
              <p className="text-xs text-slate-400">Ask someone who manages members to turn it on.</p>
            )
          }
        />
      </div>
    )
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl card-shadow p-6">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h3 className="font-semibold text-slate-900">Tax Prep Pack</h3>
          <p className="text-xs text-amber-700 font-medium mt-0.5">{DISCLAIMER}</p>
        </div>
        <select
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="text-sm rounded-lg border border-slate-300 px-2 py-1.5"
        >
          <option value={thisYear}>{thisYear}</option>
          <option value={thisYear - 1}>{thisYear - 1}</option>
        </select>
      </div>

      {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : data ? (
        <div className="mb-4">
          {workspace.type === 'group' && <GroupPreview data={data} />}
          {workspace.type === 'nonprofit' && <NonprofitPreview data={data} />}
          {workspace.type === 'business' && <BusinessPreview data={data} />}
        </div>
      ) : null}

      <div className="flex gap-2">
        <button
          onClick={handleDownloadPdf}
          disabled={generating}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {generating ? generatingMessage : 'Download PDF'}
        </button>
        <button
          onClick={handleDownloadCsv}
          className="bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium"
        >
          Download CSV
        </button>
      </div>
    </div>
  )
}
