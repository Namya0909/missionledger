import { useRef, useState } from 'react'
import { Eye, MessageCircle, X } from 'lucide-react'
import { api } from '../lib/api'
import { friendlyError } from '../lib/friendlyError'
import useRotatingMessages from '../lib/useRotatingMessages'
import BehindTheScenesPanel from './BehindTheScenesPanel'

const THINKING_MESSAGES = ['Thinking it through…', 'Checking your pots…', 'Double-checking the numbers…']

export default function ChatWidget({ workspaceId }) {
  const [open, setOpen] = useState(false)
  const [scenesOpen, setScenesOpen] = useState(false)
  const [messages, setMessages] = useState([
    { role: 'assistant', text: "Ask me things like \"how much of our grant is left?\" or \"what's our dining out total this month?\"" },
  ])
  // One entry per request sent, kept for the whole session (never cleared) so past
  // turns stay scrollable/screenshot-able in the Behind the scenes panel.
  const [turns, setTurns] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [lastFailedText, setLastFailedText] = useState(null)
  const scrollRef = useRef(null)
  const thinkingMessage = useRotatingMessages(THINKING_MESSAGES, sending)

  async function sendMessage(text) {
    setSending(true)
    try {
      const res = await api.sendChatMessage(workspaceId, text)
      setMessages((m) => [...m, { role: res.blocked ? 'blocked' : 'assistant', text: res.reply }])
      setTurns((t) => [
        ...t,
        {
          userMessage: text,
          steps: res.trace || [],
          tokens: {
            input: res.total_input_tokens || 0,
            cached: res.total_cached_tokens || 0,
            output: res.total_output_tokens || 0,
            cost: res.total_cost_usd || 0,
          },
        },
      ])
      setLastFailedText(null)
    } catch (err) {
      setMessages((m) => [...m, { role: 'blocked', text: friendlyError(err) }])
      setTurns((t) => [...t, { userMessage: text, steps: [] }])
      setLastFailedText(text)
    } finally {
      setSending(false)
      setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }), 50)
    }
  }

  async function send(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    setMessages((m) => [...m, { role: 'user', text }])
    setInput('')
    await sendMessage(text)
  }

  async function retry() {
    if (!lastFailedText || sending) return
    await sendMessage(lastFailedText)
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-end gap-3">
      {scenesOpen && <BehindTheScenesPanel turns={turns} onClose={() => setScenesOpen(false)} />}

      <div className="flex flex-col items-end">
        {open && (
          <div className="mb-3 w-[90vw] max-w-sm h-[60vh] max-h-[480px] bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col overflow-hidden">
            <div className="bg-emerald-900 text-white px-4 py-3 flex items-center justify-between">
              <span className="font-semibold text-sm">MissionLedger Assistant</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setScenesOpen((s) => !s)}
                  className="text-emerald-200 hover:text-white text-xs inline-flex items-center gap-1"
                  title="See which helpers and tools handled each request"
                >
                  <Eye size={14} /> Behind the scenes
                </button>
                <button onClick={() => setOpen(false)} className="text-emerald-200 hover:text-white">
                  <X size={16} />
                </button>
              </div>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2">
              {messages.map((m, i) => (
                <div key={i}>
                  <div
                    className={`text-sm rounded-lg px-3 py-2 max-w-[85%] ${
                      m.role === 'user'
                        ? 'bg-emerald-700 text-white ml-auto'
                        : m.role === 'blocked'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-slate-100 text-slate-800'
                    }`}
                  >
                    {m.text}
                  </div>
                  {m.role === 'blocked' && i === messages.length - 1 && lastFailedText && (
                    <button onClick={retry} className="text-xs text-emerald-700 hover:underline mt-1 ml-1">
                      Try again
                    </button>
                  )}
                </div>
              ))}
              {sending && <div className="text-xs text-slate-400 px-3">{thinkingMessage}</div>}
            </div>
            <form onSubmit={send} className="border-t border-slate-200 p-2 flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about this workspace…"
                className="flex-1 text-sm rounded-lg border border-slate-300 px-3 py-1.5"
              />
              <button
                type="submit"
                disabled={sending}
                className="bg-emerald-700 hover:bg-emerald-800 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50"
              >
                Send
              </button>
            </form>
          </div>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-14 h-14 shadow-lg flex items-center justify-center"
          aria-label="Open chat assistant"
        >
          {open ? <X size={24} /> : <MessageCircle size={24} />}
        </button>
      </div>
    </div>
  )
}
