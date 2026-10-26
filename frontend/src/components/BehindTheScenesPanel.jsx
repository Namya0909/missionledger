import { Eye, X, Zap } from 'lucide-react'

function formatArgs(args) {
  if (!args || Object.keys(args).length === 0) return null
  return Object.entries(args)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

function formatStepCost(step) {
  const hasTokens = step.input_tokens != null || step.output_tokens != null
  if (!hasTokens && step.cost_usd == null) return null
  const parts = []
  if (step.input_tokens != null) parts.push(`${step.input_tokens.toLocaleString('en-US')} in`)
  if (step.cached_tokens) parts.push(`${step.cached_tokens.toLocaleString('en-US')} cached`)
  if (step.output_tokens != null) parts.push(`${step.output_tokens.toLocaleString('en-US')} out`)
  const tokenPart = parts.join(' / ')
  const costPart = step.cost_usd != null ? `$${step.cost_usd.toFixed(4)}` : null
  return [tokenPart, costPart].filter(Boolean).join(' · ')
}

export default function BehindTheScenesPanel({ turns, onClose }) {
  return (
    <div className="mb-3 w-[90vw] max-w-sm h-[60vh] max-h-[480px] bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col overflow-hidden">
      <div className="bg-slate-800 text-white px-4 py-3 flex items-center justify-between">
        <span className="font-semibold text-sm inline-flex items-center gap-1.5">
          <Eye size={15} /> Behind the scenes
        </span>
        <button onClick={onClose} className="text-slate-300 hover:text-white">
          <X size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {turns.length === 0 && (
          <p className="text-sm text-slate-400">Ask the assistant something — each request's helpers and tool calls will show up here, and stay here so you can scroll back through them.</p>
        )}
        {turns.map((turn, i) => (
          <div key={i} className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 border-b border-slate-200 flex items-center justify-between gap-2">
              <span>"{turn.userMessage}"</span>
              {turn.tokens && (turn.tokens.input > 0 || turn.tokens.output > 0) && (
                <span className="text-slate-400 font-normal whitespace-nowrap inline-flex items-center gap-1">
                  <Zap size={11} />
                  {(turn.tokens.input + turn.tokens.output).toLocaleString('en-US')} tokens
                  {turn.tokens.cached > 0 && ` (${turn.tokens.cached.toLocaleString('en-US')} cached)`} · $
                  {turn.tokens.cost.toFixed(4)}
                </span>
              )}
            </div>
            <div className="divide-y divide-slate-100">
              {turn.steps.map((step, j) => (
                <div key={j} className="px-3 py-2 text-xs">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="font-semibold text-emerald-700">{step.helper}</span>
                    {step.tool && <span className="text-slate-400">→ {step.tool}</span>}
                  </div>
                  {formatArgs(step.args) && <div className="text-slate-500 mb-0.5">args: {formatArgs(step.args)}</div>}
                  <div className="text-slate-700 break-words">{step.result}</div>
                  {formatStepCost(step) && (
                    <div className="text-slate-400 mt-0.5 inline-flex items-center gap-1">
                      <Zap size={10} /> {formatStepCost(step)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
