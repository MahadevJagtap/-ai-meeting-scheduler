"""
LangGraph node implementations for the 4-stage scheduling workflow.

Node 1: analyze_request   – Parse NL request with gpt-4o
Node 2: retrieve_context   – Fetch calendar + memory context
Node 3: synthesize_slots   – Rank optimal time slots
Node 4: execute_scheduling  – Book meeting + trigger notifications
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta

from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq

from app.agents.state import AgentState
from app.config import get_settings
from app.memory import retrieve_relevant_preferences
from app.tools.calendar_tools import (
    check_conflicts,
    create_calendar_event,
    get_free_busy_slots,
)
from app.tools.communication_tools import send_email, send_whatsapp

logger = logging.getLogger(__name__)

_settings = get_settings()


def _extract_json(text: str) -> dict | list:
    """Resiliently extract JSON from a string that might contain markdown or text."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find content between ```json and ```
    import re
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find content between { or [ and its last counterpart
    start_idx = text.find("{")
    if start_idx == -1:
        start_idx = text.find("[")
    
    end_idx = text.rfind("}")
    if end_idx == -1:
        end_idx = text.rfind("]")
        
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            return json.loads(text[start_idx:end_idx+1])
        except json.JSONDecodeError:
            pass
            
    raise ValueError("Could not extract valid JSON from LLM response")


def _get_llm() -> ChatGroq:
    """Return a configured ChatGroq instance with llama-3.3-70b-versatile."""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        api_key=_settings.groq_api_key,
    )


# ────────────────────────────────────────────────────────────
#  NODE 1: Analyze the natural language request
# ────────────────────────────────────────────────────────────


async def analyze_request(state: AgentState) -> dict:
    """
    Parse the user's natural language meeting request using gpt-4o.
    Extracts: meeting_type, duration, date range, urgency, participants.
    """
    logger.info("Node 1: Analyzing request for user=%s", state.get("user_id"))

    llm = _get_llm()
    now_iso = datetime.now(timezone.utc).isoformat()

    system_prompt = (
        "You are a meeting scheduling assistant. Parse the user's request and "
        "extract the following fields as JSON:\n"
        "{\n"
        '  "meeting_type": "string (e.g. standup, 1:1, bug triage, team sync)",\n'
        '  "duration_minutes": integer,\n'
        '  "date_range_start": "ISO 8601 date string",\n'
        '  "date_range_end": "ISO 8601 date string",\n'
        '  "urgency": "low | medium | high",\n'
        '  "participants": ["email1@example.com"]\n'
        "}\n\n"
        f"Current UTC time: {now_iso}\n"
        f"User Timezone Offset: {state.get('timezone_offset', 0)} minutes from UTC (UTC - Local).\n"
        # Calculate and show user's local time for context
        f"User's Current Local Time: { (datetime.now(timezone.utc) - timedelta(minutes=state.get('timezone_offset', 0))).isoformat() }\n\n"
        "If the user does not specify a date range, default to the next 5 business days.\n"
        "If duration is not specified, default to 30 minutes.\n"
        "Return ONLY valid JSON, no markdown fences."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["user_request"]},
    ]

    try:
        response = await llm.ainvoke(messages)
        parsed = _extract_json(response.content)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object from analysis")

        def _ensure_rfc3339(dt_str: str, default_days: int = 0) -> str:
            if not dt_str:
                from datetime import timedelta
                dt = datetime.now(timezone.utc) + timedelta(days=default_days)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                # Try parsing and re-formatting to ensure it's Z-terminated or has offset
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                from datetime import timedelta
                dt = datetime.now(timezone.utc) + timedelta(days=default_days)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        start_dt = _ensure_rfc3339(parsed.get("date_range_start"), 0)
        end_dt = _ensure_rfc3339(parsed.get("date_range_end"), 5)

        return {
            "meeting_type": parsed.get("meeting_type", "general"),
            "duration_minutes": parsed.get("duration_minutes", 30),
            "date_range_start": start_dt,
            "date_range_end": end_dt,
            "urgency": parsed.get("urgency", "medium"),
            "participants": parsed.get("participants", state.get("participants", [])),
            "status": "retrieving",
            "messages": [
                HumanMessage(content=state["user_request"]),
                AIMessage(content=response.content),
            ],
        }
    except Exception as exc:
        logger.exception("Node 1 failed")
        return {
            "status": "error",
            "errors": [f"Analysis failed: {exc}"],
        }


# ────────────────────────────────────────────────────────────
#  NODE 2: Retrieve calendar state and memory context
# ────────────────────────────────────────────────────────────


async def retrieve_context(state: AgentState) -> dict:
    """
    Fetch free/busy slots from Google Calendar and retrieve
    relevant user preferences from sqlite.
    """
    logger.info("Node 2: Retrieving context for user=%s range=%s to %s", 
                state.get("user_id"), state.get("date_range_start"), state.get("date_range_end"))

    errors = list(state.get("errors", []))

    # ── Calendar slots ────────────────────────────────────
    calendar_slots: list[dict] = []
    try:
        slots_json = get_free_busy_slots.invoke(
            {
                "start_date": state.get("date_range_start", ""),
                "end_date": state.get("date_range_end", ""),
            }
        )
        slots_data = json.loads(slots_json)
        if "error" in slots_data:
            errors.append(f"Calendar error: {slots_data['error']}")
        else:
            calendar_slots = slots_data.get("free", [])
    except Exception as exc:
        logger.exception("Calendar retrieval failed")
        errors.append(f"Calendar retrieval error: {exc}")

    # ── User preferences (RAG) ───────────────────────────
    preferences: list[str] = []
    try:
        query_context = (
            f"{state.get('meeting_type', '')} meeting with "
            f"{', '.join(state.get('participants', []))} "
            f"urgency: {state.get('urgency', 'medium')}"
        )
        preferences = await retrieve_relevant_preferences(
            user_id=state.get("user_id", ""),
            query=query_context,
        )
    except Exception as exc:
        logger.exception("Preference retrieval failed")
        errors.append(f"Memory error: {exc}")

    return {
        "calendar_slots": calendar_slots,
        "user_preferences": preferences,
        "status": "synthesizing",
        "errors": errors,
    }


# ────────────────────────────────────────────────────────────
#  NODE 3: Synthesize optimal time slots
# ────────────────────────────────────────────────────────────


async def synthesize_slots(state: AgentState) -> dict:
    """
    Use LLM to rank available slots considering user preferences and meeting context.
    Falls back to constructing a slot from the requested time if no calendar slots exist.
    """
    logger.info("Node 3: Synthesizing slots for user=%s", state.get("user_id"))

    duration = int(state.get("duration_minutes") or 30)
    calendar_slots = state.get("calendar_slots", [])
    user_request = state.get("user_request", "")
    date_range_start = state.get("date_range_start", "")

    # ── Local fallback: build a slot from the requested time when calendar is empty ──
    if not calendar_slots:
        logger.info("No calendar slots available — building slot from requested time")
        try:
            from datetime import timedelta
            start_dt = datetime.fromisoformat(date_range_start.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(minutes=duration)
            fallback_slot = {
                "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "score": 0.85,
                "reason": "Scheduled at the user's requested time (no conflicts found in calendar).",
            }
            return {
                "suggested_slots": [fallback_slot],
                "selected_slot": fallback_slot,
                "status": "scheduling",
            }
        except Exception as exc:
            logger.warning("Fallback slot construction failed: %s", exc)

    # ── LLM-based synthesis when calendar slots are available ──
    llm = _get_llm()

    system_prompt = (
        "You are a scheduling optimizer. Given available calendar slots and user context, "
        "pick the top 3 best meeting times.\n\n"
        "CRITICAL: You MUST respond with ONLY a raw JSON array. No explanations, no markdown, no text before or after.\n"
        "Even if slots are limited, return your best picks from the available list.\n\n"
        "Format:\n"
        '[{"start": "2026-02-24T09:00:00Z", "end": "2026-02-24T09:30:00Z", "score": 0.9, "reason": "Morning slot, matches preferences"}]\n\n'
        "Rules:\n"
        "- score is 0.0 to 1.0 (higher = better)\n"
        "- Prefer slots matching user preferences\n"
        "- Prefer morning for high urgency\n"
        "- The start/end must be selected from the available_slots list\n"
        "- If fewer than 3 slots are available, return only what is available\n"
        "- RETURN ONLY THE JSON ARRAY. NOTHING ELSE."
    )

    context = (
        f"meeting_type: {state.get('meeting_type')}\n"
        f"duration_minutes: {duration}\n"
        f"urgency: {state.get('urgency')}\n"
        f"user_request: {user_request}\n"
        f"participants: {', '.join(state.get('participants', []))}\n\n"
        f"available_slots:\n{json.dumps(calendar_slots[:20], indent=2)}\n\n"
        f"user_preferences:\n"
        + "\n".join(f"- {p}" for p in state.get("user_preferences", []))
    )

    try:
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ]
        )
        suggested = _extract_json(response.content)
        if not isinstance(suggested, list):
            raise ValueError("Expected JSON array from synthesis")

        # Validate that each item has start/end
        suggested = [s for s in suggested if s.get("start") and s.get("end")]
        if not suggested:
            raise ValueError("No valid slots returned from LLM")

        # Pick the highest-scored slot
        suggested.sort(key=lambda s: s.get("score", 0), reverse=True)
        selected = suggested[0]

        return {
            "suggested_slots": suggested,
            "selected_slot": selected,
            "status": "scheduling",
            "messages": [AIMessage(content=response.content)],
        }
    except Exception as exc:
        logger.warning("LLM synthesis failed (%s), using first available slot as fallback", exc)
        # Final fallback: use the first available calendar slot directly
        if calendar_slots:
            from datetime import timedelta
            first = calendar_slots[0]
            try:
                start_dt = datetime.fromisoformat(first["start"].replace("Z", "+00:00"))
                end_dt = start_dt + timedelta(minutes=duration)
                selected = {
                    "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "score": 0.7,
                    "reason": "Best available slot from calendar.",
                }
                return {
                    "suggested_slots": [selected],
                    "selected_slot": selected,
                    "status": "scheduling",
                }
            except Exception as fe:
                logger.exception("Final fallback also failed: %s", fe)

        retry_count = state.get("retry_count", 0) + 1
        return {
            "status": "error",
            "retry_count": retry_count,
            "errors": [f"Synthesis failed: {exc}"],
        }


# ────────────────────────────────────────────────────────────
#  NODE 4: Execute scheduling and notify participants
# ────────────────────────────────────────────────────────────


async def execute_scheduling(state: AgentState) -> dict:
    """
    Book the selected slot on Google Calendar, then send
    confirmation notifications via email and WhatsApp.
    """
    logger.info("Node 4: Executing scheduling for user=%s", state.get("user_id"))

    selected = state.get("selected_slot")
    if not selected:
        return {
            "status": "error",
            "errors": ["No slot selected for scheduling"],
        }

    errors = list(state.get("errors", []))
    notifications: list[str] = []
    meeting_details: dict | None = None

    # ── Create calendar event ─────────────────────────────
    try:
        participants = state.get("participants", [])
        result_json = create_calendar_event.invoke(
            {
                "summary": f"{state.get('meeting_type', 'Meeting').title()} Meeting",
                "start": selected["start"],
                "end": selected["end"],
                "attendees": ", ".join(participants),
                "description": (
                    f"Scheduled by AI assistant.\n"
                    f"Original request: {state.get('user_request', '')}\n"
                    f"Urgency: {state.get('urgency', 'medium')}"
                ),
            }
        )
        result = json.loads(result_json)

        if result.get("success"):
            meeting_details = {
                "event_id": result.get("event_id", ""),
                "summary": f"{state.get('meeting_type', 'Meeting').title()} Meeting",
                "start": selected["start"],
                "end": selected["end"],
                "participants": participants,
                "calendar_link": result.get("html_link", ""),
            }

            # ── Schedule autonomous reminders ────────────
            try:
                from app.services.reminder_service import schedule_reminders

                await schedule_reminders(
                    event_id=result.get("event_id", ""),
                    summary=meeting_details["summary"],
                    description=state.get("user_request", ""),
                    start_time=datetime.fromisoformat(
                        selected["start"].replace("Z", "+00:00")
                    ),
                    end_time=datetime.fromisoformat(
                        selected["end"].replace("Z", "+00:00")
                    ),
                    participants=participants,
                    user_id=state.get("user_id", ""),
                )
            except Exception as exc:
                logger.exception("Failed to schedule reminders")
                errors.append(f"Reminder scheduling error: {exc}")

        else:
            errors.append(f"Calendar event creation failed: {result.get('error')}")

    except Exception as exc:
        logger.exception("Calendar event creation error")
        errors.append(f"Event creation error: {exc}")

    # ── Send notifications ────────────────────────────────
    if meeting_details:
        confirmation_msg = (
            f"✅ Your {meeting_details['summary']} has been scheduled!\n"
            f"📅 {selected['start']} → {selected['end']}\n"
            f"👥 Participants: {', '.join(meeting_details['participants'])}\n"
            f"🔗 {meeting_details.get('calendar_link', 'N/A')}"
        )

        # Build list of unique recipients (emails + whatsapp numbers)
        recipients = list(set(meeting_details.get("participants", [])))
        
        # Proactively add the user's configured WhatsApp number if not already present
        user_whatsapp = _settings.get("MY_WHATSAPP_NUMBER") if hasattr(_settings, "get") else os.getenv("MY_WHATSAPP_NUMBER")
        # Note: _settings is a Pydantic Settings object, we can access it directly
        try:
             settings_dict = _settings.model_dump()
             user_whatsapp = settings_dict.get("my_whatsapp_number")
        except:
             user_whatsapp = os.getenv("MY_WHATSAPP_NUMBER")

        if user_whatsapp and user_whatsapp not in recipients:
             recipients.append(user_whatsapp)

        for recipient in recipients:
            # Email notification (only if it looks like an email)
            if "@" in recipient:
                try:
                    await send_email.ainvoke(
                        {
                            "to": recipient,
                            "subject": f"Meeting Scheduled: {meeting_details['summary']}",
                            "body": confirmation_msg,
                        }
                    )
                    if "email" not in notifications:
                        notifications.append("email")
                except Exception:
                    logger.exception("Email notification failed for %s", recipient)

            # WhatsApp notification (if it looks like a phone number or is the user's number)
            if recipient.startswith("+") or recipient.startswith("whatsapp:") or recipient == user_whatsapp:
                try:
                    await send_whatsapp.ainvoke(
                        {"to": recipient, "message": confirmation_msg}
                    )
                    if "whatsapp" not in notifications:
                        notifications.append("whatsapp")
                except Exception:
                    logger.exception("WhatsApp notification failed for %s", recipient)

    return {
        "meeting_details": meeting_details,
        "notifications_sent": notifications,
        "status": "done" if meeting_details else "error",
        "errors": errors,
    }
