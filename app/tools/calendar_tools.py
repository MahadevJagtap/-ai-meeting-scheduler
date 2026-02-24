"""
LangChain @tool definitions for Google Calendar interactions.

These tools are bound to the LLM agent so it can autonomously:
- Query free/busy slots
- Check scheduling conflicts against working hours
- Create calendar events
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta

from langchain_core.tools import tool

from app.config import get_settings
from app.services.calendar_service import (
    create_event as _create_event,
    get_freebusy,
    list_events,
)

logger = logging.getLogger(__name__)


@tool
def get_free_busy_slots(
    start_date: str,
    end_date: str,
    calendar_id: str = "",
) -> str:
    """
    Get free and busy time slots from Google Calendar.

    Args:
        start_date: Start of the query window in ISO 8601 format (e.g. '2026-02-24T09:00:00Z').
        end_date:   End of the query window in ISO 8601 format (e.g. '2026-02-28T18:00:00Z').
        calendar_id: Optional calendar ID. Defaults to the user's primary calendar.

    Returns:
        JSON string with 'busy' slots and computed 'free' slots within working hours.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id

    try:
        result = get_freebusy(start_date, end_date, cal_id)
        busy_slots = (
            result.get("calendars", {}).get(cal_id, {}).get("busy", [])
        )

        # Compute free slots within working hours
        wh_start = datetime.strptime(settings.working_hours_start, "%H:%M").time()
        wh_end = datetime.strptime(settings.working_hours_end, "%H:%M").time()

        free_slots = _compute_free_slots(
            busy_slots,
            datetime.fromisoformat(start_date.replace("Z", "+00:00")),
            datetime.fromisoformat(end_date.replace("Z", "+00:00")),
            wh_start,
            wh_end,
        )

        return json.dumps(
            {"busy": busy_slots, "free": free_slots},
            indent=2,
            default=str,
        )
    except Exception as exc:
        logger.exception("get_free_busy_slots failed")
        return json.dumps({"error": str(exc)})


@tool
def check_conflicts(
    proposed_start: str,
    proposed_end: str,
    calendar_id: str = "",
) -> str:
    """
    Check if a proposed meeting time conflicts with existing events
    or falls outside standard working hours.

    Args:
        proposed_start: Proposed start in ISO 8601 format.
        proposed_end:   Proposed end in ISO 8601 format.
        calendar_id:    Optional calendar ID.

    Returns:
        JSON string indicating whether the slot has conflicts and details.
    """
    settings = get_settings()
    cal_id = calendar_id or settings.google_calendar_id

    try:
        wh_start = datetime.strptime(settings.working_hours_start, "%H:%M").time()
        wh_end = datetime.strptime(settings.working_hours_end, "%H:%M").time()

        prop_start = datetime.fromisoformat(proposed_start.replace("Z", "+00:00"))
        prop_end = datetime.fromisoformat(proposed_end.replace("Z", "+00:00"))

        # Working-hours check
        outside_hours = (
            prop_start.time() < wh_start
            or prop_end.time() > wh_end
            or prop_start.weekday() >= 5  # Saturday / Sunday
        )

        # Existing event overlap check
        events = list_events(proposed_start, proposed_end, cal_id)
        conflicts = []
        for event in events:
            ev_start = event.get("start", {}).get("dateTime", "")
            ev_end = event.get("end", {}).get("dateTime", "")
            conflicts.append(
                {
                    "summary": event.get("summary", "Untitled"),
                    "start": ev_start,
                    "end": ev_end,
                }
            )

        return json.dumps(
            {
                "has_conflict": len(conflicts) > 0,
                "outside_working_hours": outside_hours,
                "conflicting_events": conflicts,
                "proposed": {"start": proposed_start, "end": proposed_end},
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("check_conflicts failed")
        return json.dumps({"error": str(exc)})


@tool
def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    attendees: str = "",
    description: str = "",
) -> str:
    """
    Create a new event on Google Calendar.

    Args:
        summary:     Event title / meeting name.
        start:       Start datetime in ISO 8601 format.
        end:         End datetime in ISO 8601 format.
        attendees:   Comma-separated email addresses of participants.
        description: Meeting description or agenda.

    Returns:
        JSON string with the created event details.
    """
    try:
        # Filter for valid emails only (must contain @ and .)
        raw_list = [e.strip() for e in attendees.split(",") if e.strip()] if attendees else []
        attendee_list = [e for e in raw_list if "@" in e and "." in e]
        
        if len(attendee_list) < len(raw_list):
            logger.info("Filtered out %d non-email identifiers from attendees", len(raw_list) - len(attendee_list))

        event = _create_event(
            summary=summary,
            start=start,
            end=end,
            attendees=attendee_list,
            description=description,
        )
        return json.dumps(
            {
                "success": True,
                "event_id": event.get("id"),
                "html_link": event.get("htmlLink"),
                "summary": event.get("summary"),
                "start": event.get("start", {}).get("dateTime"),
                "end": event.get("end", {}).get("dateTime"),
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("create_calendar_event failed")
        return json.dumps({"success": False, "error": str(exc)})


# ── Internal helpers ──────────────────────────────────────────


def _compute_free_slots(
    busy_slots: list[dict],
    range_start: datetime,
    range_end: datetime,
    wh_start: time,
    wh_end: time,
) -> list[dict[str, str]]:
    """
    Given busy periods, compute free windows within working hours
    for each day in the range.
    """
    free: list[dict[str, str]] = []
    current_day = range_start.date()
    end_day = range_end.date()

    while current_day <= end_day:
        # Skip weekends
        if current_day.weekday() >= 5:
            current_day += timedelta(days=1)
            continue

        day_start = datetime.combine(current_day, wh_start, tzinfo=range_start.tzinfo)
        day_end = datetime.combine(current_day, wh_end, tzinfo=range_start.tzinfo)

        # Collect busy blocks that overlap this day
        day_busy = []
        for b in busy_slots:
            b_start = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
            b_end = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            if b_start < day_end and b_end > day_start:
                day_busy.append((max(b_start, day_start), min(b_end, day_end)))

        day_busy.sort()

        # Walk through the day and find gaps
        cursor = day_start
        for b_start, b_end in day_busy:
            if cursor < b_start:
                free.append({"start": cursor.isoformat(), "end": b_start.isoformat()})
            cursor = max(cursor, b_end)
        if cursor < day_end:
            free.append({"start": cursor.isoformat(), "end": day_end.isoformat()})

        current_day += timedelta(days=1)

    return free
