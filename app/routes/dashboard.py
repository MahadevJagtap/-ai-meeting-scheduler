"""
FastAPI routes for providing dashboard-specific data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select, func

from app.config import get_settings
from app.memory import get_all_preferences
from app.services.calendar_service import list_events

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dashboard"])

_settings = get_settings()

@router.get("/dashboard/{user_id}")
async def get_dashboard_data(user_id: str) -> dict[str, Any]:
    """
    Fetch comprehensive dashboard data including preference status 
    and upcoming calendar events.
    """
    data = {
        "preferences": {"count": 0},
        "meetings": [],
        "stats": {
            "total_meetings": 0
        },
        "systems": {
            "calendar": "unknown",
            "database": "online"
        }
    }

    # 1. Fetch Preference Count
    try:
        prefs = await get_all_preferences(user_id)
        data["preferences"]["count"] = len(prefs)
    except Exception as exc:
        logger.warning("Dashboard: Failed to fetch preferences: %s", exc)
        data["systems"]["database"] = "error"

    # 2. Fetch Meeting Count from DB
    try:
        from app.database import ScheduledMeetingRow, async_session_factory
        from sqlalchemy import func
        async with async_session_factory() as session:
            res = await session.execute(select(func.count()).select_from(ScheduledMeetingRow).where(ScheduledMeetingRow.user_id == user_id))
            data["stats"]["total_meetings"] = res.scalar() or 0
    except Exception as exc:
        logger.warning("Dashboard: Failed to fetch meeting count: %s", exc)

    # 3. Fetch Upcoming Meetings from Calendar
    try:
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        
        events = list_events(
            time_min=now.isoformat(),
            time_max=future.isoformat(),
            max_results=5
        )
        
        formatted_meetings = []
        for event in events:
            start = event.get("start", {})
            start_str = start.get("dateTime") or start.get("date") or ""
            
            dt = None
            if start_str:
                try:
                    # Handle Z or offset
                    if start_str.endswith('Z'):
                        start_str = start_str.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(start_str)
                except:
                    pass
            
            formatted_meetings.append({
                "id": event.get("id"),
                "summary": event.get("summary", "Untitled Meeting"),
                "start": start_str,
                "display_day": dt.strftime("%d") if dt else "??",
                "display_month": dt.strftime("%b") if dt else "??",
                "display_time": dt.strftime("%I:%M %p") if dt else "Unknown",
                "link": event.get("htmlLink")
            })
            
        data["meetings"] = formatted_meetings
        data["systems"]["calendar"] = "connected"
    except Exception as exc:
        logger.warning("Dashboard: Failed to fetch calendar events: %s", exc)
        data["systems"]["calendar"] = "error"

    return data
