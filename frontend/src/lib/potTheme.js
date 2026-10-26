import {
  Briefcase,
  Car,
  Coffee,
  Gift,
  Home,
  Landmark,
  PiggyBank,
  Phone,
  Receipt,
  Shield,
  ShoppingCart,
  Stethoscope,
  Target,
  Unlock,
  Users,
  Wallet,
  Wifi,
  Zap,
} from 'lucide-react'

// Keyword -> icon, checked against the pot's own name first, so "Rent" always
// gets a house, "Payroll" always gets people, etc. — falls back to a generic
// icon for the pot's type (below) when nothing matches.
const KEYWORD_ICONS = [
  [/rent|mortgage|lease/i, Home],
  [/grocer|food(?!\s*bank)/i, ShoppingCart],
  [/utilit|electric|energy|power/i, Zap],
  [/payroll|salar|staff|wage/i, Users],
  [/tax/i, Receipt],
  [/internet|wifi|comcast|broadband/i, Wifi],
  [/phone|wireless|verizon|at&t/i, Phone],
  [/coffee|cafe|catering/i, Coffee],
  [/medical|health|clinic/i, Stethoscope],
  [/donat|gift|charit/i, Gift],
  [/office|supplies|equipment/i, Briefcase],
  [/car|auto|gas|transport|fuel/i, Car],
  [/grant/i, Landmark],
]

const TYPE_FALLBACK_ICON = {
  spending: Wallet,
  savings_goal: Target,
  restricted_grant: Landmark,
  reserve: Shield,
  free_use: Unlock,
}

// One of these per pot, picked deterministically from the pot's own name, so
// every pot reads as visually distinct rather than every "Spending" pot
// looking identical. bar/solid are for the icon chip + accents; the actual
// progress-bar fill stays tied to budget status (ok/warning/over) elsewhere —
// this is purely decorative, never a signal.
const PALETTE = [
  { chip: 'bg-blue-100 text-blue-700', solid: 'bg-blue-500' },
  { chip: 'bg-orange-100 text-orange-700', solid: 'bg-orange-500' },
  { chip: 'bg-purple-100 text-purple-700', solid: 'bg-purple-500' },
  { chip: 'bg-rose-100 text-rose-700', solid: 'bg-rose-500' },
  { chip: 'bg-sky-100 text-sky-700', solid: 'bg-sky-500' },
  { chip: 'bg-indigo-100 text-indigo-700', solid: 'bg-indigo-500' },
  { chip: 'bg-teal-100 text-teal-700', solid: 'bg-teal-500' },
  { chip: 'bg-amber-100 text-amber-700', solid: 'bg-amber-500' },
  { chip: 'bg-pink-100 text-pink-700', solid: 'bg-pink-500' },
  { chip: 'bg-cyan-100 text-cyan-700', solid: 'bg-cyan-500' },
  { chip: 'bg-lime-100 text-lime-700', solid: 'bg-lime-500' },
  { chip: 'bg-violet-100 text-violet-700', solid: 'bg-violet-500' },
]

function hashString(s) {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

export function getPotTheme(pot) {
  const match = KEYWORD_ICONS.find(([re]) => re.test(pot.name))
  const Icon = match ? match[1] : TYPE_FALLBACK_ICON[pot.type] || PiggyBank
  const { chip, solid } = PALETTE[hashString(pot.name) % PALETTE.length]
  return { Icon, chip, solid }
}
