"""
FastAPI application entrypoint.

Sets up:
- Lifespan context manager (DB init, APScheduler start/stop)
- CORS middleware
- Route mounting
- Health check endpoint
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import init_db
from app.routes.chat import router as chat_router
from app.routes.preferences import router as preferences_router
from app.routes.scheduling import router as scheduling_router
from app.services.reminder_service import start_scheduler, stop_scheduler

# ── Logging ───────────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logger.info("🚀 Starting Meeting Scheduler service…")

    # Initialize database tables
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception:
        logger.exception("⚠️  Database initialization failed (will continue)")

    # Start the APScheduler for autonomous reminders
    try:
        start_scheduler()
        logger.info("✅ APScheduler started")
    except Exception:
        logger.exception("⚠️  Scheduler start failed")

    yield

    # Shutdown
    logger.info("🛑 Shutting down…")
    stop_scheduler()


# ── App Factory ───────────────────────────────────────────────

app = FastAPI(
    title="AI Meeting Scheduler",
    description=(
        "Multi-agent autonomous meeting scheduling system powered by "
        "LangGraph, OpenAI gpt-4o, Google Calendar, Sqlite, Twilio, and SMTP."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files & Templates ─────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "templates"))

# ── Routers ───────────────────────────────────────────────────

app.include_router(scheduling_router)
app.include_router(preferences_router)
app.include_router(chat_router)


# ── Health Check ──────────────────────────────────────────────


@app.api_route("/health", methods=["GET", "HEAD"], tags=["system"])
async def health_check():
    """Lightweight liveness probe for uptime monitoring (e.g. UptimeRobot)."""
    return {"status": "ok"}


# ── Frontend Route ────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def serve_frontend(request: Request):
    """Serve the Glassmorphism frontend SPA."""
    return templates.TemplateResponse("index.html", {"request": request})
