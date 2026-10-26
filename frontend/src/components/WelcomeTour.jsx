import { useState } from 'react'
import { Eye, MessageCircle, PiggyBank } from 'lucide-react'

const SLIDES = [
  {
    icon: PiggyBank,
    title: 'Pots hold your money',
    body: "Pots are where your money lives — rent, groceries, a savings goal, whatever matters to your group. Each one tracks its own balance and budget.",
  },
  {
    icon: Eye,
    title: '"Needs Attention" watches for you',
    body: "This box flags anything worth a look — overspending, a goal falling behind, an expense in the wrong category — so you don't have to go looking for it.",
  },
  {
    icon: MessageCircle,
    title: 'Just ask',
    body: 'Use the chat bubble in the corner any time. Try "how much is left in groceries?" and get a real, grounded answer pulled straight from your data.',
  },
]

export default function WelcomeTour({ onDone }) {
  const [step, setStep] = useState(0)
  const slide = SLIDES[step]
  const isLast = step === SLIDES.length - 1
  const Icon = slide.icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="bg-white rounded-xl card-shadow border border-slate-200 w-full max-w-sm p-6 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-50 text-emerald-700 mb-4">
          <Icon size={26} strokeWidth={1.75} />
        </div>
        <h2 className="text-lg font-semibold text-slate-900 mb-2">{slide.title}</h2>
        <p className="text-sm text-slate-600 leading-relaxed">{slide.body}</p>

        <div className="flex items-center justify-center gap-1.5 mt-6 mb-5">
          {SLIDES.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === step ? 'w-5 bg-emerald-700' : 'w-1.5 bg-slate-200'
              }`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button onClick={onDone} className="text-sm text-slate-500 hover:text-slate-700">
            Skip tour
          </button>
          <button
            onClick={() => (isLast ? onDone() : setStep((s) => s + 1))}
            className="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-1.5 rounded-lg text-sm font-medium"
          >
            {isLast ? 'Get started' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}
