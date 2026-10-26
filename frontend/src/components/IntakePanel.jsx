import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import useRotatingMessages from '../lib/useRotatingMessages'
import { formatUSD } from '../lib/format'

function UploadButton({ label, accept, uploading, onFile, rotatingMessages }) {
  const inputRef = useRef(null)
  const uploadingLabel = useRotatingMessages(rotatingMessages, uploading)
  return (
    <>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
      >
        {uploading ? uploadingLabel : label}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
          e.target.value = ''
        }}
      />
    </>
  )
}

export default function IntakePanel({ workspaceId, onChanged }) {
  const [pots, setPots] = useState([])

  useEffect(() => {
    api.listPots(workspaceId).then(setPots).catch(() => {})
  }, [workspaceId])

  const potNames = pots.map((p) => p.name)

  // --- Statement ---
  const [statementRows, setStatementRows] = useState(null) // [{..., include}]
  const [statementUploading, setStatementUploading] = useState(false)
  const [statementError, setStatementError] = useState('')
  const [statementSubmitting, setStatementSubmitting] = useState(false)
  const [statementLastFile, setStatementLastFile] = useState(null)

  async function handleStatementFile(file) {
    setStatementError('')
    setStatementUploading(true)
    setStatementLastFile(file)
    try {
      const res = await api.uploadStatement(workspaceId, file)
      setStatementRows(res.rows.map((r) => ({ ...r, include: true })))
    } catch (err) {
      setStatementError(friendlyError(err))
    } finally {
      setStatementUploading(false)
    }
  }

  function updateStatementRow(i, patch) {
    setStatementRows((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  async function confirmStatementRows() {
    setStatementError('')
    setStatementSubmitting(true)
    try {
      const rows = statementRows
        .filter((r) => r.include)
        .map((r) => ({
          date: r.date,
          merchant: r.merchant,
          amount: r.amount,
          pot_name: r.suggested_pot,
          category: r.suggested_category,
          source: 'uploaded_file',
        }))
      await api.confirmIntakeTransactions(workspaceId, rows)
      setStatementRows(null)
      onChanged?.()
    } catch (err) {
      setStatementError(err.message)
    } finally {
      setStatementSubmitting(false)
    }
  }

  // --- Receipt ---
  const [receipt, setReceipt] = useState(null) // extraction result, or {visionAvailable:false}
  const [receiptUploading, setReceiptUploading] = useState(false)
  const [receiptError, setReceiptError] = useState('')
  const [receiptSubmitting, setReceiptSubmitting] = useState(false)
  const [manualReceipt, setManualReceipt] = useState({ store: '', date: '', amount: '', pot_name: '', category: '' })
  const [receiptLastFile, setReceiptLastFile] = useState(null)

  async function handleReceiptFile(file) {
    setReceiptError('')
    setReceiptUploading(true)
    setReceiptLastFile(file)
    try {
      const res = await api.uploadIntakeReceipt(workspaceId, file)
      setReceipt(res)
      if (!res.vision_available) {
        setManualReceipt({ store: '', date: '', amount: '', pot_name: '', category: '' })
      }
    } catch (err) {
      setReceiptError(friendlyError(err))
    } finally {
      setReceiptUploading(false)
    }
  }

  async function confirmReceipt() {
    setReceiptError('')
    setReceiptSubmitting(true)
    try {
      const source = receipt.vision_available
        ? {
            date: receipt.date,
            merchant: receipt.store,
            amount: receipt.amount,
            pot_name: receipt.suggested_pot,
            category: receipt.suggested_category || 'Uncategorized',
          }
        : {
            date: manualReceipt.date,
            merchant: manualReceipt.store,
            amount: Number(manualReceipt.amount),
            pot_name: manualReceipt.pot_name,
            category: manualReceipt.category || 'Uncategorized',
          }
      await api.confirmIntakeTransactions(workspaceId, [{ ...source, source: 'receipt_photo' }])
      setReceipt(null)
      onChanged?.()
    } catch (err) {
      setReceiptError(err.message)
    } finally {
      setReceiptSubmitting(false)
    }
  }

  // --- Grant PDF ---
  const [grant, setGrant] = useState(null)
  const [grantUploading, setGrantUploading] = useState(false)
  const [grantError, setGrantError] = useState('')
  const [grantSubmitting, setGrantSubmitting] = useState(false)
  const [grantLastFile, setGrantLastFile] = useState(null)

  async function handleGrantFile(file) {
    setGrantError('')
    setGrantUploading(true)
    setGrantLastFile(file)
    try {
      const res = await api.uploadGrantPdf(workspaceId, file)
      setGrant({ ...res, pot_name: res.grant_name })
    } catch (err) {
      setGrantError(friendlyError(err))
    } finally {
      setGrantUploading(false)
    }
  }

  async function confirmGrant() {
    setGrantError('')
    setGrantSubmitting(true)
    try {
      await api.confirmIntakeGrant(workspaceId, {
        pot_name: grant.pot_name,
        grantor: grant.grantor,
        amount: grant.amount,
        start_date: grant.start_date,
        end_date: grant.end_date,
        allowed_categories: grant.allowed_categories,
        disallowed_categories: grant.disallowed_categories,
        report_deadlines: grant.report_deadlines,
      })
      setGrant(null)
      onChanged?.()
    } catch (err) {
      setGrantError(err.message)
    } finally {
      setGrantSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        Upload a bank statement, a receipt, or a grant agreement and MissionLedger reads it for you.
      </p>

      {/* Statement */}
      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <h3 className="font-semibold text-slate-900 mb-1">Bank / Credit Card Statement</h3>
        <p className="text-xs text-slate-500 mb-3">Upload a Chase or Bank of America-style CSV export. Nothing is saved until you confirm below.</p>
        <UploadButton
          label="Upload statement CSV"
          accept=".csv,text/csv"
          uploading={statementUploading}
          onFile={handleStatementFile}
          rotatingMessages={['Reading your statement…', 'Matching transactions to pots…', 'Almost done…']}
        />
        {statementError && (
          <p className="text-sm text-rose-600 mt-2">
            {statementError}{' '}
            {statementLastFile && (
              <button onClick={() => handleStatementFile(statementLastFile)} className="text-emerald-700 hover:underline font-medium">
                Try again
              </button>
            )}
          </p>
        )}

        {statementRows && (
          <div className="mt-4 space-y-2">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                    <th className="py-1 pr-2"></th>
                    <th className="py-1 pr-2">Date</th>
                    <th className="py-1 pr-2">Merchant</th>
                    <th className="py-1 pr-2">Amount</th>
                    <th className="py-1 pr-2">Pot</th>
                    <th className="py-1 pr-2">Category</th>
                  </tr>
                </thead>
                <tbody>
                  {statementRows.map((row, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-1 pr-2">
                        <input type="checkbox" checked={row.include} onChange={(e) => updateStatementRow(i, { include: e.target.checked })} />
                      </td>
                      <td className="py-1 pr-2 text-slate-600">{row.date}</td>
                      <td className="py-1 pr-2 text-slate-800">{row.merchant}</td>
                      <td className="py-1 pr-2 text-slate-800">{formatUSD(row.amount)}</td>
                      <td className="py-1 pr-2">
                        <select
                          value={row.suggested_pot}
                          onChange={(e) => updateStatementRow(i, { suggested_pot: e.target.value })}
                          className="text-xs rounded border border-slate-300 px-1 py-0.5"
                        >
                          <option value="Unmatched">Unmatched</option>
                          {potNames.map((n) => (
                            <option key={n} value={n}>{n}</option>
                          ))}
                        </select>
                      </td>
                      <td className="py-1 pr-2">
                        <input
                          value={row.suggested_category}
                          onChange={(e) => updateStatementRow(i, { suggested_category: e.target.value })}
                          className="text-xs rounded border border-slate-300 px-1 py-0.5 w-28"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmStatementRows}
                disabled={statementSubmitting}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {statementSubmitting ? 'Adding…' : `Add ${statementRows.filter((r) => r.include).length} expenses`}
              </button>
              <button onClick={() => setStatementRows(null)} className="text-sm text-slate-500 hover:underline">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Receipt */}
      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <h3 className="font-semibold text-slate-900 mb-1">Receipt Photo</h3>
        <p className="text-xs text-slate-500 mb-3">Upload a photo of a receipt (JPEG, PNG, or WEBP).</p>
        <UploadButton
          label="Upload receipt photo"
          accept="image/jpeg,image/png,image/webp"
          uploading={receiptUploading}
          onFile={handleReceiptFile}
          rotatingMessages={['Reading your receipt…', 'Figuring out the category…']}
        />
        {receiptError && (
          <p className="text-sm text-rose-600 mt-2">
            {receiptError}{' '}
            {receiptLastFile && (
              <button onClick={() => handleReceiptFile(receiptLastFile)} className="text-emerald-700 hover:underline font-medium">
                Try again
              </button>
            )}
          </p>
        )}

        {receipt && !receipt.vision_available && (
          <div className="mt-4 space-y-2">
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{receipt.message}</p>
            <div className="grid grid-cols-2 gap-2">
              <input placeholder="Store" value={manualReceipt.store} onChange={(e) => setManualReceipt((m) => ({ ...m, store: e.target.value }))} className="text-sm rounded-lg border border-slate-300 px-2 py-1.5" />
              <input type="date" value={manualReceipt.date} onChange={(e) => setManualReceipt((m) => ({ ...m, date: e.target.value }))} className="text-sm rounded-lg border border-slate-300 px-2 py-1.5" />
              <input type="number" step="0.01" placeholder="Amount" value={manualReceipt.amount} onChange={(e) => setManualReceipt((m) => ({ ...m, amount: e.target.value }))} className="text-sm rounded-lg border border-slate-300 px-2 py-1.5" />
              <select value={manualReceipt.pot_name} onChange={(e) => setManualReceipt((m) => ({ ...m, pot_name: e.target.value }))} className="text-sm rounded-lg border border-slate-300 px-2 py-1.5">
                <option value="">Choose a pot</option>
                {potNames.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              <input placeholder="Category" value={manualReceipt.category} onChange={(e) => setManualReceipt((m) => ({ ...m, category: e.target.value }))} className="text-sm rounded-lg border border-slate-300 px-2 py-1.5 col-span-2" />
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmReceipt}
                disabled={receiptSubmitting || !manualReceipt.store || !manualReceipt.date || !manualReceipt.amount || !manualReceipt.pot_name}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {receiptSubmitting ? 'Adding…' : 'Add expense'}
              </button>
              <button onClick={() => setReceipt(null)} className="text-sm text-slate-500 hover:underline">Cancel</button>
            </div>
          </div>
        )}

        {receipt && receipt.vision_available && (
          <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <label className="text-xs text-slate-500">Store
                <input value={receipt.store || ''} onChange={(e) => setReceipt((r) => ({ ...r, store: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1" />
              </label>
              <label className="text-xs text-slate-500">Date
                <input type="date" value={receipt.date || ''} onChange={(e) => setReceipt((r) => ({ ...r, date: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1" />
              </label>
              <label className="text-xs text-slate-500">Amount
                <input type="number" step="0.01" value={receipt.amount ?? ''} onChange={(e) => setReceipt((r) => ({ ...r, amount: Number(e.target.value) }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1" />
              </label>
              <label className="text-xs text-slate-500">Pot
                <select value={receipt.suggested_pot || ''} onChange={(e) => setReceipt((r) => ({ ...r, suggested_pot: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1">
                  <option value="">Choose a pot</option>
                  {potNames.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
            {receipt.items?.length > 0 && <p className="text-xs text-slate-500">Items: {receipt.items.join(', ')}</p>}
            <div className="flex gap-2">
              <button
                onClick={confirmReceipt}
                disabled={receiptSubmitting || !receipt.suggested_pot || !receipt.store || !receipt.date || !receipt.amount}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {receiptSubmitting ? 'Adding…' : 'Add expense'}
              </button>
              <button onClick={() => setReceipt(null)} className="text-sm text-slate-500 hover:underline">Cancel</button>
            </div>
          </div>
        )}
      </div>

      {/* Grant PDF */}
      <div className="bg-white border border-slate-200 rounded-xl card-shadow p-4">
        <h3 className="font-semibold text-slate-900 mb-1">Grant Agreement PDF</h3>
        <p className="text-xs text-slate-500 mb-3">Upload a grant agreement letter to pull out the amount, dates, rules, and report deadlines, then create a pot for it.</p>
        <UploadButton
          label="Upload grant PDF"
          accept="application/pdf"
          uploading={grantUploading}
          onFile={handleGrantFile}
          rotatingMessages={['Reading the grant agreement…', 'Pulling out the key terms…']}
        />
        {grantError && (
          <p className="text-sm text-rose-600 mt-2">
            {grantError}{' '}
            {grantLastFile && (
              <button onClick={() => handleGrantFile(grantLastFile)} className="text-emerald-700 hover:underline font-medium">
                Try again
              </button>
            )}
          </p>
        )}

        {grant && (
          <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
            <label className="block text-xs text-slate-500">Pot name
              <input value={grant.pot_name} onChange={(e) => setGrant((g) => ({ ...g, pot_name: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-slate-500">Grantor
                <input value={grant.grantor || ''} onChange={(e) => setGrant((g) => ({ ...g, grantor: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" />
              </label>
              <label className="text-xs text-slate-500">Amount
                <input type="number" step="0.01" value={grant.amount ?? ''} onChange={(e) => setGrant((g) => ({ ...g, amount: Number(e.target.value) }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" />
              </label>
              <label className="text-xs text-slate-500">Start date
                <input type="date" value={grant.start_date || ''} onChange={(e) => setGrant((g) => ({ ...g, start_date: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" />
              </label>
              <label className="text-xs text-slate-500">End date
                <input type="date" value={grant.end_date || ''} onChange={(e) => setGrant((g) => ({ ...g, end_date: e.target.value }))} className="mt-0.5 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" />
              </label>
            </div>
            <p className="text-xs text-slate-500">Allowed: {grant.allowed_categories.join(', ') || 'none specified'}</p>
            <p className="text-xs text-slate-500">Disallowed: {grant.disallowed_categories.join(', ') || 'none specified'}</p>
            {grant.report_deadlines.length > 0 && (
              <p className="text-xs text-slate-500">
                Report deadlines: {grant.report_deadlines.map((d) => `${d.description} by ${d.date}`).join('; ')}
              </p>
            )}
            <div className="flex gap-2">
              <button
                onClick={confirmGrant}
                disabled={grantSubmitting || !grant.pot_name}
                className="bg-emerald-700 hover:bg-emerald-800 text-white px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {grantSubmitting ? 'Creating…' : 'Create pot'}
              </button>
              <button onClick={() => setGrant(null)} className="text-sm text-slate-500 hover:underline">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
