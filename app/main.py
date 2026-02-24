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


@app.get("/health", tags=["system"])
async def health_check():
    """Diagnostic probe for all core integrations."""
    from sqlalchemy import text
    from app.database import engine
    from app.services.calendar_service import _get_calendar_service
    
    # 1. Database Check
    db_status = "unknown"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"unreachable ({exc})"

    # 2. Groq Check
    groq_status = "configured" if settings.groq_api_key else "missing API key"
    
    # 3. Calendar Check
    calendar_status = "unknown"
    try:
        _get_calendar_service()
        calendar_status = "ready"
    except Exception as exc:
        calendar_status = f"error ({exc})"

    overall = "healthy"
    if db_status != "connected" or groq_status != "configured" or "error" in calendar_status:
        overall = "degraded"

    return {
        "status": overall,
        "service": "ai-meeting-scheduler",
        "database": db_status,
        "groq_api": groq_status,
        "calendar": calendar_status,
        "environment": settings.app_env,
        "version": "1.0.2",
    }


# ── Frontend Route ────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def serve_frontend(request: Request):
    """Serve the Glassmorphism frontend SPA."""
    return templates.TemplateResponse("index.html", {"request": request})
