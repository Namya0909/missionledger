"""In-memory sliding-window rate limiting — per-process, resets on restart.
That's a real tradeoff (no Redis/shared store here), acceptable for this
single-instance SQLite demo app; called out explicitly rather than implied to
be production-grade. The persistent, security-critical control (locking an
account after repeated wrong passwords) lives on the User row in models.py
instead, precisely because that one needs to survive a restart.
"""

import time
from collections import defaultdict, deque

_windows: dict[str, deque] = defaultdict(deque)


def _prune(key: str, window_seconds: int) -> deque:
    window = _windows[key]
    cutoff = time.monotonic() - window_seconds
    while window and window[0] < cutoff:
        window.popleft()
    return window


def check_sliding_window(key: str, *, limit: int, window_seconds: int) -> bool:
    """Returns True if this call is allowed, False if it would exceed `limit`
    calls within the last `window_seconds` for this key. Allowed calls are
    recorded; calls that would be rejected are not (so a client hammering the
    limit doesn't keep extending its own lockout window). Use this when every
    call should count toward the limit regardless of outcome (e.g. chat
    messages) — for cases where only failures should count (e.g. login), use
    `is_rate_limited` + `record_attempt` instead."""
    window = _prune(key, window_seconds)
    if len(window) >= limit:
        return False
    window.append(time.monotonic())
    return True


def is_rate_limited(key: str, *, limit: int, window_seconds: int) -> bool:
    """Peek only — does not record a new attempt. Use before doing the actual
    work, so a caller can decide whether to even try (and whether to record
    an attempt) based on the outcome."""
    return len(_prune(key, window_seconds)) >= limit


def record_attempt(key: str, *, window_seconds: int) -> None:
    _prune(key, window_seconds)
    _windows[key].append(time.monotonic())
