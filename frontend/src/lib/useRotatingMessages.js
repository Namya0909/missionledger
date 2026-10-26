import { useEffect, useState } from 'react'

// Cycles through `messages` every `intervalMs` while `active` is true, resetting
// to the first message each time a new wait starts. Purely cosmetic — these are
// honest "here's roughly what's happening" labels, not a real progress signal,
// since the underlying calls are single request/response, not streaming.
export default function useRotatingMessages(messages, active, intervalMs = 1400) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!active) {
      setIndex(0)
      return
    }
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % messages.length)
    }, intervalMs)
    return () => clearInterval(id)
  }, [active, messages, intervalMs])

  return messages[index]
}
