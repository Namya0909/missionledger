"""A 10-minute TTL cache for chat replies, keyed by (workspace_id, exact message).
In-memory/per-process, same tradeoff as ratelimit.py. Only used when the
`response_cache` feature flag is on — reusing an answer verbatim is a real,
measurable savings but changes behavior (a question asked twice in a row won't
re-check the latest data), so it stays opt-in and clearly labeled in the trace
when it fires.
"""

import time

TTL_SECONDS = 10 * 60

_cache: dict[tuple[int, str], tuple[float, object]] = {}


def get(workspace_id: int, message: str):
    key = (workspace_id, message)
    entry = _cache.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if time.monotonic() - stored_at > TTL_SECONDS:
        del _cache[key]
        return None
    return value


def set(workspace_id: int, message: str, value) -> None:
    _cache[(workspace_id, message)] = (time.monotonic(), value)


def clear() -> None:
    _cache.clear()
