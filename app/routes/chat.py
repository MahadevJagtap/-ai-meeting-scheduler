"""
FastAPI route for the conversational chat interface.

Handles:
- General queries ("hello", "list my meetings", "what can you do?")
- Meeting scheduling requests (delegates to the scheduling workflow)
- Calendar queries (list upcoming meetings)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter
from groq import AsyncGroq
from pydantic import BaseModel

from app.config import get_settings
from app.services.calendar_service import _get_calendar_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

_settings = get_settings()
_groq = AsyncGroq(api_key=_settings.groq_api_key)

SCHEDULE_KEYWORDS = [
    "schedule", "book", "set up", "arrange", "create a meeting",
    "plan a meeting", "add meeting", "organise", "organize",
    "block time", "reserve", "make an appointment",
]

CALENDAR_KEYWORDS = [
    "list", "show", "what meetings", "my meetings", "upcoming",
    "calendar", "events today", "events tomorrow", "what do i have",
    "my schedule", "my events", "next meeting", "when is my", "which is my",
]


class ChatRequest(BaseModel):
    user_id: str = "default_user"
    message: str
    participants: list[str] = []
    timezone_offset: int = 0


class ChatResponse(BaseModel):
    reply: str
    intent: str  # "schedule" | "calendar" | "general"
    schedule_payload: dict | None = None  # if intent == "schedule"


def _detect_intent(msg: str) -> str:
    lower = msg.lower()
    for kw in SCHEDULE_KEYWORDS:
        if kw in lower:
            return "schedule"
    for kw in CALENDAR_KEYWORDS:
        if kw in lower:
            return "calendar"
    return "general"


async def _list_upcoming_meetings() -> str:
    """Fetch upcoming events from Google Calendar."""
    try:
        service = _get_calendar_service()
        cal_id = _settings.google_calendar_id or "primary"
        now_iso = datetime.now(timezone.utc).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=now_iso,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return "📅 Your calendar is clear — no upcoming meetings found."

        lines = ["📅 **Your upcoming meetings:**\n"]
        for e in events:
            start = e.get("start", {})
            start_str = start.get("dateTime") or start.get("date") or "Unknown time"
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start_str = dt.strftime("%a, %d %b %Y at %I:%M %p")
            except Exception:
                pass
            lines.append(f"• **{e.get('summary', 'Untitled')}** — {start_str}")

        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Calendar list failed: %s", exc)
        return f"⚠️ Could not load calendar events: {exc}"


async def _general_chat(message: str, user_id: str) -> str:
    """Use Groq LLM to handle general conversation."""
    system = (
        "You are a helpful AI meeting assistant. "
        "You help users schedule meetings, check their calendar, and answer general questions. "
        "Be concise, friendly, and professional. "
        "If the user wants to schedule a meeting, ask them for details like title, date, time, and duration. "
        "Do NOT return JSON. Just respond conversationally."
    )
    response = await _groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].message.content or "I'm here to help! What would you like to do?"


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Intelligent chat endpoint that routes to the appropriate handler."""
    msg = payload.message.strip()
    intent = _detect_intent(msg)

    if intent == "calendar":
        reply = await _list_upcoming_meetings()
        return ChatResponse(reply=reply, intent="calendar")

    if intent == "schedule":
        # Build a schedule_payload for the frontend to use
        return ChatResponse(
            reply=(
                "📅 I'll schedule that for you! Processing your request now...\n\n"
                "_(Connecting to the scheduling agent…)_"
            ),
            intent="schedule",
            schedule_payload={
                "user_id": payload.user_id,
                "request_text": msg,
                "participants": payload.participants,
                "timezone_offset": payload.timezone_offset,
            },
        )

    # General query
    reply = await _general_chat(msg, payload.user_id)
    return ChatResponse(reply=reply, intent="general")
