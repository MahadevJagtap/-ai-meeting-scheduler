"""
Google Calendar API service wrapper.

Handles authentication and provides async-friendly methods for:
- Fetching free/busy information
- Listing upcoming events
- Creating new calendar events
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Build and return a Google Calendar API service instance (OAuth2 or Service Account)."""
    settings = get_settings()
    creds_val = settings.google_calendar_credentials_json

    # 1. Try OAuth2 User Flow (preferred with current credentials.json)
    if os.path.exists("token.json"):
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

    # 2. Try loading from credentials string as JSON OR path
    try:
        trimmed_val = creds_val.strip()
        if not trimmed_val or trimmed_val == "{}":
            raise ValueError("GOOGLE_CALENDAR_CREDENTIALS_JSON is empty or default '{}'")

        if trimmed_val.startswith("{"):
            # It's a JSON string
            actual_json = trimmed_val
        elif os.path.exists(trimmed_val):
            # It's a file path
            with open(trimmed_val, "r") as f:
                actual_json = f.read()
        else:
            # It's a path that doesn't exist
            raise FileNotFoundError(f"Credentials file not found at: {trimmed_val}")
        
        creds_info = json.loads(actual_json)
        
        # Detect if it's a Service Account or OAuth Client ID
        if "type" in creds_info and creds_info["type"] == "service_account":
            credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return build("calendar", "v3", credentials=credentials)
        elif "installed" in creds_info or "web" in creds_info:
            # This is OAuth Client ID, but no token.json exists.
            raise RuntimeError(
                "OAuth2 Client ID detected but 'token.json' is missing. "
                "Please run 'pa\\Scripts\\python setup_calendar_oauth.py' once to authorize."
            )
        else:
            raise ValueError("Unknown credential type in JSON")

    except Exception as exc:
        logger.error(f"Calendar authentication failed: {exc}")
        raise


def get_freebusy(
    time_min: str,
    time_max: str,
    calendar_id: str | None = None,
) -> dict[str, Any]:
    """
    Query Google Calendar for free/busy windows.

    Args:
        time_min: RFC3339 start of the query window.
        time_max: RFC3339 end of the query window.
        calendar_id: Calendar to check (defaults to configured primary).

    Returns:
        The raw freebusy response body from the API.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": cal_id}],
    }

    result = service.freebusy().query(body=body).execute()
    logger.info("FreeBusy query %s → %s: %d busy blocks", time_min, time_max, len(result.get("calendars", {}).get(cal_id, {}).get("busy", [])))
    return result


def list_events(
    time_min: str,
    time_max: str,
    calendar_id: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List upcoming events within a time range."""
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

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

    Args:
        summary: Event title.
        start: RFC3339 start datetime.
        end: RFC3339 end datetime.
        attendees: List of email addresses.
        description: Event description.
        calendar_id: Target calendar.

    Returns:
        The created event resource from the API.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id
    service = _get_calendar_service()

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
