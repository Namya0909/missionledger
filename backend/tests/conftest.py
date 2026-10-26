"""Shared pytest fixtures for the whole suite.

The trick: `database.py` builds its `engine`/`SessionLocal` from `config.DATABASE_URL`
at import time, and every router/module does `from database import SessionLocal`
(or `get_db`) at ITS OWN import time. So to run against an isolated test database
instead of the real `missionledger.db`, we have to repoint `database.engine`/
`database.SessionLocal` BEFORE anything else (routers, seed.py, main.py) gets
imported for the first time in this process — that's why this file imports
`database` first, patches it, and only then imports `main`. Every later
`from database import SessionLocal` (in seed.py, recurring.py, etc.) then
resolves to the already-patched test session factory.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB_PATH = BACKEND_DIR / "test_missionledger.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()  # start every test run from a clean, freshly-seeded DB

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import database  # noqa: E402

test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
database.engine = test_engine
database.SessionLocal = TestingSessionLocal

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
from main import app  # noqa: E402

HAS_AI_KEY = bool(config.PORTKEY_API_KEY or config.OPENAI_API_KEY)
requires_ai_key = pytest.mark.skipif(
    not HAS_AI_KEY,
    reason="No PORTKEY_API_KEY/OPENAI_API_KEY configured — skipping tests that need a real AI call.",
)

DEMO_PASSWORD = "demo1234"
# Matches seed.py's DEMO_SECURITY_ANSWERS — every demo/seeded account uses these.
DEMO_SECURITY_ANSWERS = {"color": "Blue", "pet": "Dog", "food": "Pizza"}


@pytest.fixture(scope="session")
def client():
    # The `with` form runs FastAPI's startup event (init_db + seed_demo_data +
    # generate_due_charges) against our patched test engine — one real, fully
    # seeded database, exactly like a grader would get running the real app.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_session(client):
    """A raw session on the same test database, for tests that want to read
    seeded ORM objects directly (e.g. the rules-checker tests) without going
    through the API/AI layer at all. Depends on `client` (even though it never
    uses it) purely to force the startup-event seeding to run first — otherwise
    a test file that only uses `db_session` could run against an empty, never-
    seeded database depending on test execution order."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def login(client, email: str, password: str = DEMO_PASSWORD) -> str:
    """Performs both login steps (password, then the account's 3 security
    answers) for a seeded demo account — every seeded account uses
    DEMO_SECURITY_ANSWERS (see seed.py), so this works for any demo email."""
    r1 = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r1.status_code == 200, f"login({email!r}) step 1 failed: {r1.status_code} {r1.text}"
    step1 = r1.json()
    answers = [{"question_key": q["key"], "answer": DEMO_SECURITY_ANSWERS[q["key"]]} for q in step1["questions"]]
    r2 = client.post(
        "/api/auth/login/verify-security",
        json={"login_ticket": step1["login_ticket"], "answers": answers},
    )
    assert r2.status_code == 200, f"login({email!r}) step 2 failed: {r2.status_code} {r2.text}"
    return r2.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def my_workspace_id(client, headers: dict) -> int:
    r = client.get("/api/workspaces", headers=headers)
    assert r.status_code == 200
    workspaces = r.json()
    assert workspaces, "expected this demo user to belong to at least one workspace"
    return workspaces[0]["id"]
