import { useRef, useState } from 'react'
import { Paperclip } from 'lucide-react'
import { api } from '../lib/api'

export default function ReceiptButton({ workspaceId, transaction, onUploaded }) {
  const inputRef = useRef(null)
  const [viewing, setViewing] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      await api.uploadReceipt(workspaceId, transaction.id, file)
      onUploaded()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function handleView() {
    try {
      const result = await api.getReceiptObjectUrl(workspaceId, transaction.id)
      setViewing(result)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      {transaction.has_receipt ? (
        <button onClick={handleView} className="text-xs text-emerald-700 hover:underline inline-flex items-center gap-1">
          <Paperclip size={12} /> Receipt
        </button>
      ) : (
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="text-xs text-slate-500 hover:underline disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : '+ Receipt'}
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        onChange={handleFile}
        className="hidden"
      />
      {error && <span className="text-xs text-rose-600">{error}</span>}

      {viewing && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setViewing(null)}
        >
          <div className="bg-white rounded-lg p-2 max-w-lg max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            {viewing.isPdf ? (
              <iframe src={viewing.url} title="Receipt" className="w-[70vw] h-[70vh]" />
            ) : (
              <img src={viewing.url} alt="Receipt" className="max-w-full max-h-[75vh]" />
            )}
            <button
              onClick={() => setViewing(null)}
              className="mt-2 text-sm text-slate-600 hover:underline block mx-auto"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </span>
  )
}
