import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ai.core import GlobalAIBudgetExceeded
from config import PROJECT_DIR, MissingAIKeyError
from database import SessionLocal, init_db
from recurring import generate_due_charges

logger = logging.getLogger(__name__)
from routers import (
    ai_usage,
    approvals,
    attention,
    auditlog,
    auth,
    chat,
    costs as costs_router,
    feature_flags as feature_flags_router,
    feedback,
    health as health_router,
    intake,
    invites,
    memberships,
    pots,
    recurring as recurring_router,
    reports as reports_router,
    security as security_router,
    setup as setup_router,
    tax_pack as tax_pack_router,
    transactions,
    workspaces,
)
from routers import settleup as settleup_router
from seed import seed_demo_data

# Set by render.yaml in production; absent locally, where /docs staying open is fine.
IS_PRODUCTION = os.getenv("MISSIONLEDGER_ENV") == "production"

app = FastAPI(
    title="MissionLedger API",
    debug=False,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Only needed when running the Vite dev server separately (npm run dev) during
# development. The production build is served by this same app (see below).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    # Harmless over plain HTTP in local dev; only takes effect once served over HTTPS.
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_demo_data()
    db = SessionLocal()
    try:
        generate_due_charges(db)
    finally:
        db.close()


@app.exception_handler(MissingAIKeyError)
async def missing_ai_key_handler(request: Request, exc: MissingAIKeyError) -> JSONResponse:
    # Thrown by config.require_ai_key() when no PORTKEY_API_KEY/OPENAI_API_KEY is set.
    # Deliberately NOT a handler for plain RuntimeError: pydantic_ai's own
    # provider-error classes (timeouts, auth failures, rate limits) all subclass
    # RuntimeError too, and those should surface as ordinary 500s, not this message.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(GlobalAIBudgetExceeded)
async def global_budget_handler(request: Request, exc: GlobalAIBudgetExceeded) -> JSONResponse:
    # Thrown by ai/core.py's check_global_budget() once today's app-wide token
    # total (shared across everyone, not any one person's own limit) hits
    # GLOBAL_DAILY_TOKEN_LIMIT. Every non-AI feature is untouched by this.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak a traceback or internal detail to the client — log the real
    # error server-side, return a flat, generic message to the caller.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


# Every API route lives under /api so it can never collide with a client-side React
# Router path (e.g. the frontend's /workspaces/3 page vs. the API's GET /workspaces/3).
# Without this prefix, a browser refresh on /workspaces/3 hit this backend route
# directly and showed raw JSON instead of the app.
API_PREFIX = "/api"
app.include_router(health_router.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(workspaces.router, prefix=API_PREFIX)
app.include_router(memberships.router, prefix=API_PREFIX)
app.include_router(pots.router, prefix=API_PREFIX)
app.include_router(transactions.router, prefix=API_PREFIX)
app.include_router(feedback.router, prefix=API_PREFIX)
app.include_router(ai_usage.router, prefix=API_PREFIX)
app.include_router(attention.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(settleup_router.router, prefix=API_PREFIX)
app.include_router(recurring_router.router, prefix=API_PREFIX)
app.include_router(auditlog.router, prefix=API_PREFIX)
app.include_router(setup_router.router, prefix=API_PREFIX)
app.include_router(invites.router, prefix=API_PREFIX)
app.include_router(intake.router, prefix=API_PREFIX)
app.include_router(reports_router.router, prefix=API_PREFIX)
app.include_router(tax_pack_router.router, prefix=API_PREFIX)
app.include_router(security_router.router, prefix=API_PREFIX)
app.include_router(costs_router.router, prefix=API_PREFIX)
app.include_router(feature_flags_router.router, prefix=API_PREFIX)


SAMPLES_DIR = PROJECT_DIR / "samples"
if SAMPLES_DIR.exists():
    # Lets the signup page link directly to real, downloadable sample files
    # (e.g. /samples/boa_statement_sample.csv) instead of only working locally.
    app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    # React Router routes (e.g. /login, /workspaces/3) are client-side only — they don't
    # correspond to real files, so any path not matching a static file or an API route
    # above falls back to index.html and lets the client router take it from there.
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:

    @app.get("/", response_class=HTMLResponse)
    def no_frontend_build() -> str:
        return (
            "<h1>MissionLedger API is running</h1>"
            "<p>No frontend build found at frontend/dist. Run "
            "<code>cd frontend && npm install && npm run build</code>, "
            "or visit <a href='/docs'>/docs</a> for the API.</p>"
        )
