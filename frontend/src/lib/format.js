export function formatUSD(amount) {
  const value = Number(amount ?? 0)
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function formatUSDate(isoDateOrDatetime) {
  if (!isoDateOrDatetime) return ''
  const d = new Date(isoDateOrDatetime)
  return d.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
