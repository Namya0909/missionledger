"""Central place for all settings: .env lookup, AI/Portkey config, and DB path.

Per course rules, the app may use ONLY two key names: PORTKEY_API_KEY
(course key, gpt-6-luna via Portkey) or OPENAI_API_KEY (your own key).
"""

from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent          # "final project/"
PARENT_DIR = PROJECT_DIR.parent           # one folder above the project

# Check the project folder first, then one level above it (e.g. where a
# professor keeps a shared .env for several student projects).
_ENV_CANDIDATES = [PROJECT_DIR / ".env", PARENT_DIR / ".env"]
ENV_PATH = next((p for p in _ENV_CANDIDATES if p.exists()), None)

if ENV_PATH:
    load_dotenv(ENV_PATH)
else:
    # Still call load_dotenv() in case keys are set another way (e.g. shell env).
    load_dotenv()

import os  # noqa: E402  (after load_dotenv so os.getenv sees the loaded values)

PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AI_MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Price list, per 1,000 tokens, keyed by model name — every cost figure in the
# app (AIUsageLog.cost_usd, the Costs page, the benchmark) is computed from the
# real token counts the API returns, multiplied by whatever is in this dict.
#
# IMPORTANT — PRICE UNKNOWN: gpt-6-luna is a course-specific model name proxied
# through Portkey. I (the AI building this) have no way to look up its real
# per-token billing rate — the numbers below are a rough placeholder estimate
# carried over from early in the project, not a real quote. Replace all three
# values once you have the actual rate (check your course's Portkey dashboard,
# or ask course staff) — every dollar figure already stored and displayed will
# be wrong by whatever factor these placeholders are off by, so this is the one
# number in the whole app you should not present as fact without updating it.
MODEL_PRICING = {
    "gpt-6-luna": {
        "input_per_1k": 0.0025,
        "cached_input_per_1k": 0.00125,
        "output_per_1k": 0.01,
    },
}

DB_PATH = PROJECT_DIR / "missionledger.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

UPLOADS_DIR = PROJECT_DIR / "uploads" / "receipts"

JWT_SECRET_ENV_VAR = "MISSIONLEDGER_JWT_SECRET"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 8  # logins expire after 8 hours


class MissingAIKeyError(RuntimeError):
    """Raised only when no AI key is configured at all — distinct from RuntimeError
    because pydantic_ai's own provider-error classes (auth failures, rate limits,
    timeouts) also happen to subclass RuntimeError. Callers that want to tell "no
    key configured" apart from "the provider call itself failed" must catch this
    exact class, not RuntimeError."""


def require_ai_key() -> None:
    """Raise a clear error if neither AI key is configured."""
    if not PORTKEY_API_KEY and not OPENAI_API_KEY:
        searched = " or ".join(str(p) for p in _ENV_CANDIDATES)
        raise MissingAIKeyError(
            "No AI key found. Set PORTKEY_API_KEY (course key) or OPENAI_API_KEY "
            f"(your own key) in a .env file at one of: {searched}. "
            "Copy .env.example to .env and fill in a value."
        )


def using_portkey() -> bool:
    return bool(PORTKEY_API_KEY)
