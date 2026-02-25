"""
Async PostgreSQL database layer.

Provides:
- Async SQLAlchemy engine and session factory.
- ORM models for `user_preferences` and `scheduled_meetings`.
- `init_db()` to create tables.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Engine & Session ──────────────────────────────────────────

_settings = get_settings()

_db_url = _settings.async_database_url

# Log a masked version of the URL for diagnostics
_masked = _db_url
if "@" in _masked:
    _masked = _masked.split("@", 1)
    _masked = f"***@{_masked[1]}"
logger.info("Database URL (masked): %s", _masked)

engine = create_async_engine(
    _db_url,
    echo=(_settings.app_env == "development"),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_recycle=300,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ── ORM Base ──────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────


class UserPreferenceRow(Base):
    """Stores user scheduling preferences."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    preference_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class ScheduledMeetingRow(Base):
    """Tracks meetings created by the system for reminder scheduling."""

    __tablename__ = "scheduled_meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    event_id = Column(String(256), nullable=False, unique=True)
    summary = Column(Text, nullable=False)
    description = Column(Text, default="")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    participants = Column(Text, default="")  # comma-separated emails
    reminder_24h_sent = Column(Integer, default=0)
    reminder_15m_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now(), nullable=False)


# ── Initialization ────────────────────────────────────────────


async def init_db() -> None:
    """Create all tables. Logs detailed errors if connection fails."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as exc:
        logger.error("Database init_db failed: %s", exc, exc_info=True)
        raise
