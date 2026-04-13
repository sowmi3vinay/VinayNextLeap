"""
Phase 6 — Runnable FastAPI app (mounts Phase 5 routes + static UI under ``/ui/``).

Run from repo root::

    uvicorn phase_6.main:app --reload --host 127.0.0.1 --port 8000

The Hugging Face dataset is **not** loaded during startup (that download can take minutes
and would keep the browser on “connection refused” until it finished). It loads on the
first ``POST /recommend`` instead; the home page and ``/ui/`` are available immediately.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from phase_1.config import PROJECT_ROOT
from phase_5.api import router as recommend_router


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
VERCEL_ORIGIN_REGEX = os.getenv(
    "VERCEL_ORIGIN_REGEX",
    r"https://.*\.vercel\.app",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Intentionally empty: restaurant data loads lazily in ``phase_5.deps.get_restaurant_df``.
    yield


app = FastAPI(
    title="Zomato-style restaurant recommendations",
    lifespan=lifespan,
)

# Add CORS middleware for frontend deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=VERCEL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend_router)

_WEB_DIR = PROJECT_ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount(
        "/ui",
        StaticFiles(directory=str(_WEB_DIR), html=True),
        name="ui",
    )


@app.get("/", include_in_schema=False)
def root_redirect():
    """Send browsers to the static tester UI when present."""
    if _WEB_DIR.is_dir():
        return RedirectResponse(url="/ui/")
    return RedirectResponse(url="/docs")
