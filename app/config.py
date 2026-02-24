"""
Centralized application settings loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groq ──────────────────────────────────────────────
    groq_api_key: str = ""

    # ── PostgreSQL ────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/meeting_scheduler"

    # ── Google Calendar ───────────────────────────────────
    google_calendar_credentials_json: str = "{}"
    google_calendar_id: str = "primary"

    # ── Twilio ────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # ── SMTP ──────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # ── App ───────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    working_hours_start: str = "09:00"
    working_hours_end: str = "18:00"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
