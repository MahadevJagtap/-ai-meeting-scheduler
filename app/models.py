"""
Pydantic models for API requests, responses, and internal data transfer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request / Response Models ────────────────────────────────


class ScheduleRequest(BaseModel):
    """Incoming natural-language scheduling request from the frontend."""

    user_id: str = Field(..., description="Unique identifier for the user")
    request_text: str = Field(
        ..., description="Natural language description of the meeting to schedule"
    )
    participants: list[str] = Field(
        default_factory=list,
        description="Email addresses of meeting participants",
    )
    timezone_offset: int = Field(
        default=0,
        description="User's timezone offset in minutes from UTC (e.g. 330 for +5:30)",
    )


class TimeSlot(BaseModel):
    """A single available or proposed time window."""

    start: datetime
    end: datetime
    score: float = Field(
        default=0.0,
        description="Ranking score (higher = better fit for user preferences)",
    )


class MeetingDetails(BaseModel):
    """Finalized meeting information after scheduling."""

    event_id: str = ""
    summary: str = ""
    description: str = ""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    calendar_link: str = ""


class ScheduleResponse(BaseModel):
    """Response returned to the frontend after the scheduling workflow runs."""

    success: bool
    message: str
    meeting: Optional[MeetingDetails] = None
    suggested_slots: list[TimeSlot] = Field(default_factory=list)


# ── User Preference Models ───────────────────────────────────


class UserPreferenceCreate(BaseModel):
    """Payload for creating a new user preference."""

    user_id: str
    preference_text: str = Field(
        ..., description="E.g. 'I prefer not to meet on Friday afternoons'"
    )


class UserPreferenceOut(BaseModel):
    """Serialized user preference returned from the API."""

    id: int
    user_id: str
    preference_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
