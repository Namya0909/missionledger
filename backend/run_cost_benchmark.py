"""Cost-savings benchmark — runs the same 20 chat tasks against a live
MissionLedger server twice (every savings flag OFF, then every flag ON),
and for each task checks the AI's reply against an independently-computed
Python/DB ground truth (same rules.pot_usage() math the app itself uses,
and a plain sum over Transaction rows for the spending-total tasks — no AI
involved in computing any expected value here).

Writes one row per (mode, task) to benchmark_results.csv in the project
root, and prints a summary: total tokens/cost per mode, % saved, and the
correctness rate per mode (must be 100% in both — a flag that saves tokens
by breaking answers is a failure, not a win).

Run with the preview server already up:
    source .venv/bin/activate && python3 run_cost_benchmark.py

Note: feature_flags.py and response_cache.py are in-memory and per-process
on the SERVER, not this script, so flags are flipped here via the real
/api/feature-flags endpoint (never imported directly) and genuinely affect
the next live chat call. Re-running this script against a server that
wasn't restarted may show an inflated cache-hit rate in the ON run, since
leftover cache entries from a prior ON run are still warm.
"""

import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "http://localhost:8000/api"
BACKEND_DIR = Path(__file__).resolve().parent
OUT_CSV = BACKEND_DIR.parent / "benchmark_results.csv"

sys.path.insert(0, str(BACKEND_DIR))

import models  # noqa: E402
from database import SessionLocal  # noqa: E402
from feature_flags import FLAG_DESCRIPTIONS  # noqa: E402
from rules import pot_usage  # noqa: E402

TOKEN_CACHE: dict[str, str] = {}


def login(email: str, password: str = "demo1234") -> str:
    if email not in TOKEN_CACHE:
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise RuntimeError(f"login({email!r}) failed: {r.status_code} {r.text}")
        TOKEN_CACHE[email] = r.json()["access_token"]
    return TOKEN_CACHE[email]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def workspace_id_for(email: str) -> int:
    token = login(email)
    return requests.get(f"{BASE}/workspaces", headers=auth(token)).json()[0]["id"]


def set_all_flags(enabled: bool) -> None:
    token = login("maya@demo.org")  # any privileged-anywhere user would do; maya is admin of her group
    for name in FLAG_DESCRIPTIONS:
        r = requests.put(f"{BASE}/feature-flags/{name}", headers=auth(token), json={"enabled": enabled})
        if r.status_code != 200:
            raise RuntimeError(f"failed to set flag {name}: {r.status_code} {r.text}")


# ---------------------------------------------------------------------------
# Ground truth — same math as the app itself (rules.pot_usage / a plain sum
# over approved transactions), computed directly against the DB. No AI call
# anywhere in this section.
# ---------------------------------------------------------------------------

def expected_pot_amount(pot_name: str) -> float:
    db = SessionLocal()
    try:
        pot = db.query(models.Pot).filter(models.Pot.name == pot_name).first()
        if pot is None:
            raise ValueError(f"no pot named {pot_name!r} in the demo data")
        txns = db.query(models.Transaction).filter(models.Transaction.pot_id == pot.id).all()
        usage = pot_usage(pot, txns, date.today())
        # "How much is left" = remaining room under a limit for a budget/grant pot;
        # for a reserve/savings pot (which builds UP, not down) it's what's
        # currently held — matching ai/orchestrator.py's own python_prefilter logic.
        if usage.limit is not None and usage.period in ("this month", "lifetime"):
            return round(usage.limit - usage.used, 2)
        return round(usage.used, 2)
    finally:
        db.close()


def expected_pot_alltime_total(pot_name: str) -> float:
    """Mirrors ai/chat.py's get_recent_transactions tool exactly for a single pot
    (no status filter, no date filter — every transaction ever recorded against
    that pot, which is what its category-subtotal fallback sums over)."""
    db = SessionLocal()
    try:
        pot = db.query(models.Pot).filter(models.Pot.name == pot_name).first()
        if pot is None:
            raise ValueError(f"no pot named {pot_name!r} in the demo data")
        txns = db.query(models.Transaction).filter(models.Transaction.pot_id == pot.id).all()
        return round(sum(t.amount for t in txns), 2)
    finally:
        db.close()


def expected_recent_spending(workspace_name: str, days: int = 30) -> float:
    """Mirrors ai/chat.py's get_spending_total tool exactly (rolling N-day window,
    not calendar month) — the AI answers "spending this month" with that tool, so
    the ground truth here has to use the same window to mean the same thing."""
    db = SessionLocal()
    try:
        ws = db.query(models.Workspace).filter(models.Workspace.name == workspace_name).first()
        if ws is None:
            raise ValueError(f"no workspace named {workspace_name!r}")
        since = date.today() - timedelta(days=days)
        txns = db.query(models.Transaction).filter(
            models.Transaction.workspace_id == ws.id,
            models.Transaction.status == models.TransactionStatus.approved,
            models.Transaction.date >= since,
        ).all()
        return round(sum(t.amount for t in txns), 2)
    finally:
        db.close()


_AMOUNT_RE = re.compile(r"-?\$?\s*([0-9][0-9,]*\.?[0-9]*)")


def reply_matches_amount(reply: str, expected: float, tolerance: float | None = None) -> bool:
    """True if some dollar figure in the reply is within tolerance of expected.
    Loose on purpose — the reply's wording/rounding isn't fixed, only the
    underlying number is what we're checking against Python's own math."""
    tol = tolerance if tolerance is not None else max(0.02, abs(expected) * 0.01)
    for match in _AMOUNT_RE.findall(reply):
        try:
            value = float(match.replace(",", ""))
        except ValueError:
            continue
        if abs(value - expected) <= tol:
            return True
    return False


# ---------------------------------------------------------------------------
# The 20 tasks — a mix of pot-balance lookups (exercises python_prefilter,
# cache_friendly_prompts, short_gatekeeper), exact-duplicate repeats within
# the run (exercises response_cache), and listing/total questions with more
# than a handful of matching transactions (exercises category_totals).
# ---------------------------------------------------------------------------

TASKS = [
    # Oak Street House (group) — maya@demo.org / josh@demo.org
    ("oak-1", "maya@demo.org", "Oak Street House", "How much is left in Rent?", lambda: expected_pot_amount("Rent")),
    ("oak-2", "maya@demo.org", "Oak Street House", "How much is left in Rent?", lambda: expected_pot_amount("Rent")),  # duplicate -> cache
    ("oak-3", "maya@demo.org", "Oak Street House", "How much is left in Groceries?", lambda: expected_pot_amount("Groceries")),
    ("oak-4", "maya@demo.org", "Oak Street House", "How much is left in Utilities?", lambda: expected_pot_amount("Utilities")),
    ("oak-5", "maya@demo.org", "Oak Street House", "How much is left in Groceries?", lambda: expected_pot_amount("Groceries")),  # duplicate -> cache
    ("oak-6", "josh@demo.org", "Oak Street House", "How much is left in Rent?", lambda: expected_pot_amount("Rent")),  # same workspace+message, different user -> still a cache hit
    ("oak-7", "josh@demo.org", "Oak Street House", "How much have we saved so far toward the Weekend Trip goal?", lambda: expected_pot_amount("Weekend Trip")),
    ("oak-8", "maya@demo.org", "Oak Street House", "Across every Groceries transaction we've ever recorded (not just this month), what's the category breakdown and grand total?", lambda: expected_pot_alltime_total("Groceries")),
    ("oak-9", "josh@demo.org", "Oak Street House", "What's our total spending in the last 30 days?", lambda: expected_recent_spending("Oak Street House")),
    ("oak-10", "maya@demo.org", "Oak Street House", "How much is left in Utilities?", lambda: expected_pot_amount("Utilities")),  # duplicate of oak-4 -> cache

    # Elm Street Community Food Bank (nonprofit) — treasurer@demo.org / volunteer@demo.org
    ("elm-1", "treasurer@demo.org", "Elm Street Community Food Bank", "How much is left in the Hunger Relief Grant?", lambda: expected_pot_amount("Hunger Relief Grant")),
    ("elm-2", "treasurer@demo.org", "Elm Street Community Food Bank", "How much is left in the Hunger Relief Grant?", lambda: expected_pot_amount("Hunger Relief Grant")),  # duplicate -> cache
    ("elm-3", "volunteer@demo.org", "Elm Street Community Food Bank", "How much is left in the City Youth Meals Grant?", lambda: expected_pot_amount("City Youth Meals Grant")),
    ("elm-4", "treasurer@demo.org", "Elm Street Community Food Bank", "How much is left in the General Fund?", lambda: expected_pot_amount("General Fund")),
    ("elm-5", "volunteer@demo.org", "Elm Street Community Food Bank", "What's our total spending in the last 30 days?", lambda: expected_recent_spending("Elm Street Community Food Bank")),  # duplicate of elm-6 -> cache
    ("elm-6", "treasurer@demo.org", "Elm Street Community Food Bank", "What's our total spending in the last 30 days?", lambda: expected_recent_spending("Elm Street Community Food Bank")),

    # Corner Coffee Co. (business) — owner@demo.org / staff@demo.org
    ("cc-1", "owner@demo.org", "Corner Coffee Co.", "How much is left in Payroll?", lambda: expected_pot_amount("Payroll")),
    ("cc-2", "owner@demo.org", "Corner Coffee Co.", "How much is left in Payroll?", lambda: expected_pot_amount("Payroll")),  # duplicate -> cache
    ("cc-3", "staff@demo.org", "Corner Coffee Co.", "How much is in Sales Tax Savings?", lambda: expected_pot_amount("Sales Tax Savings")),
    ("cc-4", "owner@demo.org", "Corner Coffee Co.", "How much is in the Emergency Reserve right now?", lambda: expected_pot_amount("Emergency Reserve")),
]

assert len(TASKS) == 20, f"expected 20 tasks, got {len(TASKS)}"


def run_task(task_id, email, workspace_name, message, expected_fn):
    ws_id = workspace_id_for(email)
    token = login(email)
    r = requests.post(f"{BASE}/workspaces/{ws_id}/chat", headers=auth(token), json={"message": message})
    if r.status_code != 200:
        return {
            "task_id": task_id, "workspace": workspace_name, "message": message,
            "expected": None, "correct": False, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0,
            "cost_usd": 0.0, "reply_snippet": f"HTTP {r.status_code}: {r.text[:150]}",
        }
    body = r.json()
    reply = body.get("reply", "")
    expected = expected_fn()
    correct = reply_matches_amount(reply, expected)
    return {
        "task_id": task_id,
        "workspace": workspace_name,
        "message": message,
        "expected": expected,
        "correct": correct,
        "input_tokens": body.get("total_input_tokens", 0),
        "cached_tokens": body.get("total_cached_tokens", 0),
        "output_tokens": body.get("total_output_tokens", 0),
        "cost_usd": body.get("total_cost_usd", 0.0),
        "reply_snippet": reply[:150],
    }


def run_mode(mode_name: str, flags_on: bool) -> list[dict]:
    set_all_flags(flags_on)
    print(f"\n--- Mode: {mode_name} (flags {'ON' if flags_on else 'OFF'}) ---")
    rows = []
    for task_id, email, workspace_name, message, expected_fn in TASKS:
        row = run_task(task_id, email, workspace_name, message, expected_fn)
        row["mode"] = mode_name
        rows.append(row)
        mark = "OK" if row["correct"] else "WRONG"
        print(
            f"  [{mark:>5}] {task_id:<8} in={row['input_tokens']:>5} cached={row['cached_tokens']:>4} "
            f"out={row['output_tokens']:>4} cost=${row['cost_usd']:.5f}  expected={row['expected']}  "
            f"reply={row['reply_snippet']!r}"
        )
    return rows


def main():
    print(f"Running {len(TASKS)} tasks against {BASE}, once with savings OFF and once with savings ON.\n")

    off_rows = run_mode("savings_off", flags_on=False)
    on_rows = run_mode("savings_on", flags_on=True)
    set_all_flags(False)  # leave the server back in the default/baseline state

    all_rows = off_rows + on_rows
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["mode", "task_id", "workspace", "message", "expected", "correct",
                        "input_tokens", "cached_tokens", "output_tokens", "cost_usd", "reply_snippet"],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    def summarize(rows, label):
        n = len(rows)
        avg_in = sum(r["input_tokens"] for r in rows) / n
        avg_cached = sum(r["cached_tokens"] for r in rows) / n
        avg_out = sum(r["output_tokens"] for r in rows) / n
        avg_cost = sum(r["cost_usd"] for r in rows) / n
        total_cost = sum(r["cost_usd"] for r in rows)
        correct_rate = 100 * sum(r["correct"] for r in rows) / n
        print(
            f"{label:<14} avg/task: {avg_in:>7.1f} in, {avg_cached:>6.1f} cached, {avg_out:>5.1f} out, "
            f"${avg_cost:.5f} cost   total cost=${total_cost:.5f}   correct={correct_rate:.0f}%"
        )
        return avg_in, avg_cached, avg_out, avg_cost, total_cost

    print("\n" + "=" * 90)
    print(f"Wrote {len(all_rows)} rows to {OUT_CSV}")
    print("=" * 90)
    off_avg_in, off_avg_cached, off_avg_out, off_avg_cost, off_total_cost = summarize(off_rows, "savings OFF")
    on_avg_in, on_avg_cached, on_avg_out, on_avg_cost, on_total_cost = summarize(on_rows, "savings ON")
    print("=" * 90)
    if off_total_cost:
        print(f"Cost cut by savings: {100 * (1 - on_total_cost / off_total_cost):.1f}%")
    off_total_tokens = (off_avg_in + off_avg_out) * len(off_rows)
    on_total_tokens = (on_avg_in + on_avg_out) * len(on_rows)
    if off_total_tokens:
        print(f"Tokens cut by savings: {100 * (1 - on_total_tokens / off_total_tokens):.1f}%")

    off_by_task = {r["task_id"]: r for r in off_rows}
    on_by_task = {r["task_id"]: r for r in on_rows}
    regressions = [tid for tid in off_by_task if off_by_task[tid]["correct"] and not on_by_task[tid]["correct"]]
    off_wrong = [tid for tid, r in off_by_task.items() if not r["correct"]]
    on_wrong = [tid for tid, r in on_by_task.items() if not r["correct"]]
    print(f"Wrong with savings OFF: {off_wrong or 'none'}")
    print(f"Wrong with savings ON:  {on_wrong or 'none'}")
    print(f"Regressions (right OFF, wrong ON): {regressions or 'none'}")


if __name__ == "__main__":
    main()
