#!/usr/bin/env python3
"""Single entry point: `python run.py` starts the whole app (API + built frontend).

No npm required to run this — the frontend is pre-built into frontend/dist/
and served as static files by the same FastAPI app.
"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    # Hosting platforms like Render assign a port and expect the app to bind to
    # it via $PORT — falls back to 8000 for local runs, where nothing sets it.
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting MissionLedger on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, app_dir=str(BACKEND_DIR))
