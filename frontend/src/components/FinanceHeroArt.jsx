// A small original illustration (not a photo) — a laptop showing a rising bar
// chart, a coin, and a checkmark badge — in the app's own brand colors, so the
// landing/login pages have real visual interest without pulling in external
// stock imagery (licensing, weight, and an inconsistent look otherwise).
export default function FinanceHeroArt({ className = '' }) {
  return (
    <svg viewBox="0 0 440 320" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <circle cx="220" cy="160" r="150" fill="#ecfdf5" />
      <circle cx="355" cy="70" r="26" fill="#fef3c7" />
      <circle cx="60" cy="230" r="18" fill="#dbeafe" />

      {/* Laptop base */}
      <rect x="90" y="190" width="260" height="14" rx="7" fill="#0f766e" />
      <rect x="110" y="70" width="220" height="128" rx="10" fill="#065f46" />
      <rect x="120" y="80" width="200" height="108" rx="4" fill="#f8fafc" />

      {/* Bar chart on screen */}
      <rect x="140" y="140" width="20" height="36" rx="3" fill="#a7f3d0" />
      <rect x="170" y="120" width="20" height="56" rx="3" fill="#6ee7b7" />
      <rect x="200" y="100" width="20" height="76" rx="3" fill="#34d399" />
      <rect x="230" y="128" width="20" height="48" rx="3" fill="#6ee7b7" />
      <path d="M140 148 L170 122 L200 102 L230 132" stroke="#047857" strokeWidth="3" strokeLinecap="round" fill="none" />

      {/* Coin */}
      <circle cx="300" cy="150" r="22" fill="#fbbf24" stroke="#d97706" strokeWidth="2" />
      <text x="300" y="157" textAnchor="middle" fontSize="20" fontWeight="700" fill="#92400e">$</text>

      {/* Checkmark badge, floating top-right of the laptop */}
      <circle cx="345" cy="95" r="26" fill="#10b981" stroke="white" strokeWidth="4" />
      <path d="M333 95 L342 104 L359 85" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" fill="none" />

      {/* Small floating receipt/card */}
      <rect x="50" y="110" width="54" height="68" rx="8" fill="white" stroke="#cbd5e1" strokeWidth="2" transform="rotate(-8 77 144)" />
      <rect x="60" y="124" width="34" height="5" rx="2.5" fill="#94a3b8" transform="rotate(-8 77 144)" />
      <rect x="60" y="136" width="34" height="5" rx="2.5" fill="#cbd5e1" transform="rotate(-8 77 144)" />
      <rect x="60" y="148" width="22" height="5" rx="2.5" fill="#cbd5e1" transform="rotate(-8 77 144)" />
    </svg>
  )
}
