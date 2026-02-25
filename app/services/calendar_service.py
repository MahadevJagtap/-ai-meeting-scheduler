"""
Google Calendar API service wrapper.

Handles authentication and provides async-friendly methods for:
- Fetching free/busy information
- Listing upcoming events
- Creating new calendar events

Graceful degradation: returns None / empty results when credentials
are not configured, so the rest of the application keeps working.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Cache so we only log the warning once
_calendar_unavailable_logged = False


def _get_calendar_service():
    """
    Build and return a Google Calendar API service instance.

    Returns None (instead of raising) when credentials are not
    configured, so callers can degrade gracefully.
    """
    global _calendar_unavailable_logged
    settings = get_settings()
    creds_val = settings.google_calendar_credentials_json

    # 1. Try OAuth2 token (preferred when token.json exists)
    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open("token.json", "w") as token_file:
                        token_file.write(creds.to_json())
                except Exception:
                    logger.warning("Failed to refresh token.json")
            if creds and creds.valid:
                return build("calendar", "v3", credentials=creds)
        except Exception as exc:
            logger.warning("token.json exists but failed to load: %s", exc)

    # 2. Try loading from GOOGLE_CALENDAR_CREDENTIALS_JSON env var
    try:
        trimmed_val = (creds_val or "").strip()

        # Not configured at all → graceful None
        if not trimmed_val or trimmed_val == "{}":
            if not _calendar_unavailable_logged:
                logger.warning(
                    "GOOGLE_CALENDAR_CREDENTIALS_JSON is empty or default '{}'. "
                    "Calendar features will be unavailable."
                )
                _calendar_unavailable_logged = True
            return None

        if trimmed_val.startswith("{"):
            # It's an inline JSON string (the correct production setup)
            actual_json = trimmed_val
        elif os.path.exists(trimmed_val):
            # It's a local file path (dev only)
            with open(trimmed_val, "r") as f:
                actual_json = f.read()
        else:
            # It's a path that doesn't exist (common misconfiguration on Render)
            if not _calendar_unavailable_logged:
                logger.warning(
                    "GOOGLE_CALENDAR_CREDENTIALS_JSON is set to '%s' but that file "
                    "does not exist. Set it to the full JSON content instead. "
                    "Calendar features will be unavailable.",
                    trimmed_val,
                )
                _calendar_unavailable_logged = True
            return None

        creds_info = json.loads(actual_json)

        # Service Account
        if creds_info.get("type") == "service_account":
            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=SCOPES
            )
            return build("calendar", "v3", credentials=credentials)

        # OAuth Client ID (installed / web)
        if "installed" in creds_info or "web" in creds_info:
            if not _calendar_unavailable_logged:
                logger.warning(
                    "OAuth2 Client ID detected but 'token.json' is missing. "
                    "Run setup_calendar_oauth.py locally to authorise, then "
                    "paste the token JSON into the GOOGLE_CALENDAR_TOKEN_JSON env var. "
                    "Calendar features will be unavailable."
                )
                _calendar_unavailable_logged = True
            return None

        logger.warning("Unknown credential type in JSON — calendar unavailable.")
        return None

    except json.JSONDecodeError as exc:
        logger.error("GOOGLE_CALENDAR_CREDENTIALS_JSON is not valid JSON: %s", exc)
        return None
    except Exception as exc:
        logger.error("Calendar authentication failed: %s", exc)
        return None


# ── Public API (all safe to call even when service is None) ───


def get_freebusy(
    time_min: str,
    time_max: str,
    calendar_id: str | None = None,
) -> dict[str, Any]:
    """
    Query Google Calendar for free/busy windows.

    Returns an empty-calendars dict when the service is unavailable.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

    if service is None:
        raise RuntimeError("Google Calendar is not configured")

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": cal_id}],
    }

    result = service.freebusy().query(body=body).execute()
    logger.info(
        "FreeBusy query %s → %s: %d busy blocks",
        time_min,
        time_max,
        len(result.get("calendars", {}).get(cal_id, {}).get("busy", [])),
    )
    return result


def list_events(
    time_min: str,
    time_max: str,
    calendar_id: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List upcoming events within a time range. Returns [] when unavailable."""
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

    if service is None:
        raise RuntimeError("Google Calendar is not configured")

    events_result = (
        service.events()
        .list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = events_result.get("items", [])
    logger.info("Listed %d events between %s and %s", len(items), time_min, time_max)
    return items


def create_event(
    summary: str,
    start: str,
    end: str,
    attendees: list[str] | None = None,
    description: str = "",
    calendar_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a new Google Calendar event.

    Raises RuntimeError when the calendar service is unavailable.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

    if service is None:
        raise RuntimeError("Google Calendar is not configured — cannot create event")

    event_body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }

    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    event = (
        service.events()
        .insert(calendarId=cal_id, body=event_body, sendUpdates="all")
        .execute()
    )
    logger.info("Created event id=%s summary=%r", event.get("id"), summary)
    return event
