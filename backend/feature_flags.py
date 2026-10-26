"""Five independently toggleable cost-saving measures, each one a plain boolean.
In-memory and per-process (resets on restart) — same tradeoff as ratelimit.py,
appropriate for a single-instance demo app and for a benchmark script that wants
to flip flags between two runs of the same process.

Every flag defaults to OFF, representing the "naive" baseline the benchmark
compares against. Toggle via the Costs page's Savings panel, or directly from
a script (`set_enabled("response_cache", True)`) for benchmarking.
"""

FLAG_DESCRIPTIONS = {
    "cache_friendly_prompts": "Keep each agent's unchanging instructions as a stable prefix so the provider can cache and discount repeated tokens (OFF simulates the common mistake of rebuilding the prompt fresh every time).",
    "short_gatekeeper": "Use a condensed Gatekeeper prompt and cap its answer to ~8 words.",
    "python_prefilter": "Answer simple 'how much is left in <pot>' questions directly from the database in Python, skipping the Gatekeeper and Orchestrator entirely.",
    "category_totals": "Send the AI category subtotals instead of every individual transaction, once there are more than a few.",
    "response_cache": "Reuse the answer to an identical question asked again within 10 minutes, instead of calling the AI again.",
}

_flags: dict[str, bool] = {name: False for name in FLAG_DESCRIPTIONS}


def is_enabled(name: str) -> bool:
    return _flags.get(name, False)


def set_enabled(name: str, value: bool) -> None:
    if name not in _flags:
        raise KeyError(f"Unknown feature flag: {name}")
    _flags[name] = value


def all_flags() -> dict[str, bool]:
    return dict(_flags)


def set_all(value: bool) -> None:
    """Used by the benchmark script to flip every flag at once between runs."""
    for name in _flags:
        _flags[name] = value
