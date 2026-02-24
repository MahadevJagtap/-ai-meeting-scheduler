"""
FastAPI route: POST /api/schedule

Triggers the LangGraph scheduling workflow from a frontend request.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.agents.state import AgentState
from app.models import (
    MeetingDetails,
    ScheduleRequest,
    ScheduleResponse,
    TimeSlot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scheduling"])


@router.post("/schedule", response_model=ScheduleResponse)
async def schedule_meeting(request: ScheduleRequest) -> ScheduleResponse:
    """
    Accept a natural-language scheduling request, run it through the
    LangGraph multi-agent workflow, and return the result.
    """
    logger.info("Schedule request from user=%s: %r", request.user_id, request.request_text[:100])

    # Prepare initial state
    initial_state: AgentState = {
        "messages": [],
        "user_request": request.request_text,
        "user_id": request.user_id,
        "participants": request.participants,
        "timezone_offset": request.timezone_offset,
        "status": "analyzing",
        "errors": [],
        "retry_count": 0,
    }

    try:
        # Execute the full LangGraph workflow with persistence
        from app.agents.graph import run_workflow
        final_state = await run_workflow(initial_state, thread_id=request.user_id)
    except Exception as exc:
        logger.exception("LangGraph execution failed")
        raise HTTPException(status_code=500, detail=f"Scheduling workflow error: {exc}")

    # ── Map final state to response ───────────────────────
    errors = final_state.get("errors", [])
    status = final_state.get("status", "error")
    meeting_raw = final_state.get("meeting_details")

    meeting = None
    if meeting_raw:
        meeting = MeetingDetails(
            event_id=meeting_raw.get("event_id", ""),
            summary=meeting_raw.get("summary", ""),
            start=_parse_dt(meeting_raw.get("start")),
            end=_parse_dt(meeting_raw.get("end")),
            participants=meeting_raw.get("participants", []),
            calendar_link=meeting_raw.get("calendar_link", ""),
        )

    suggested = [
        TimeSlot(
            start=_parse_dt(s.get("start")),
            end=_parse_dt(s.get("end")),
            score=s.get("score", 0.0),
        )
        for s in final_state.get("suggested_slots", [])
        if s.get("start") and s.get("end")
    ]

    if status == "done":
        message = "Meeting scheduled successfully!"
        if final_state.get("notifications_sent"):
            channels = ", ".join(final_state["notifications_sent"])
            message += f" Notifications sent via {channels}."
    else:
        message = "Scheduling could not be completed."
        if errors:
            message += f" Errors: {'; '.join(errors)}"

    return ScheduleResponse(
        success=(status == "done"),
        message=message,
        meeting=meeting,
        suggested_slots=suggested,
    )


def _parse_dt(value: str | None) -> datetime | None:
    """Safely parse an ISO datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
