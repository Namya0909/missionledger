const GENERIC_FALLBACK = "Something went wrong on our end. Please try again in a moment."

// Most backend error messages are already short, plain sentences (checked at
// every raise site — e.g. "File is too large (max 5 MB)") and should pass
// through unchanged. This only catches the technical-looking ones: a stack
// trace, raw JSON, a browser network error, or anything unusually long.
export function friendlyError(err) {
  const msg = err?.message || ''
  if (!msg) return GENERIC_FALLBACK
  const looksTechnical = /traceback|exception|<html|undefined is not|failed to fetch|networkerror/i.test(msg) || msg.length > 180
  return looksTechnical ? GENERIC_FALLBACK : msg
}
