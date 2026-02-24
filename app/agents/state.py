"""
LangGraph agent state definition.

This TypedDict flows through every node in the scheduling graph,
accumulating information as each node processes it.
"""

from __future__ import annotations

from typing import Any, Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """Shared state passed between all LangGraph nodes."""

    # ── Conversation history ──────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Input ─────────────────────────────────────────────
    user_request: str          # Original natural-language request
    user_id: str               # Requesting user's identifier
    timezone_offset: int       # Minutes from UTC

    # ── Parsed intent (Node 1 output) ────────────────────
    meeting_type: str          # e.g. "standup", "1:1", "bug triage"
    duration_minutes: int      # Desired meeting length
    date_range_start: str      # ISO date string – earliest acceptable date
    date_range_end: str        # ISO date string – latest acceptable date
    urgency: str               # "low" | "medium" | "high"
    participants: list[str]    # Email list of attendees

    # ── Context (Node 2 output) ──────────────────────────
    calendar_slots: list[dict[str, Any]]      # Free/busy windows from Google Calendar
    user_preferences: list[str]               # Retrieved preference texts from pgvector

    # ── Synthesis (Node 3 output) ────────────────────────
    suggested_slots: list[dict[str, Any]]     # Ranked candidate time slots
    selected_slot: dict[str, Any] | None      # The chosen slot

    # ── Execution (Node 4 output) ────────────────────────
    meeting_details: dict[str, Any] | None    # Created event details
    notifications_sent: list[str]             # Channels notified ("email", "whatsapp")

    # ── Control flow ─────────────────────────────────────
    status: str                # "analyzing" | "retrieving" | "synthesizing" | "scheduling" | "done" | "error"
    errors: list[str]          # Accumulated error messages
    retry_count: int           # Number of synthesis retries (for conflict loops)
