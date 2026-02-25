"""
Autonomous reminder service using APScheduler.

Schedules context-aware reminders at 24 hours and 10 minutes before
each meeting, delivered via Email and WhatsApp.
Uses Groq LLM to generate natural-language reminder messages.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from groq import AsyncGroq
from sqlalchemy import select, update

from app.config import get_settings
from app.database import ScheduledMeetingRow, async_session_factory
from app.tools.communication_tools import send_email, send_whatsapp

logger = logging.getLogger(__name__)

_settings = get_settings()
_groq = AsyncGroq(api_key=_settings.groq_api_key)

# ── Scheduler singleton ──────────────────────────────────────

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the APScheduler background loop."""
    if not scheduler.running:
        # Check for pending reminders every 60 seconds
        scheduler.add_job(
            _check_and_send_reminders,
            "interval",
            seconds=60,
            id="reminder_checker",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started – reminder checker running every 60s")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


# ── Schedule reminders for a new meeting ─────────────────────


async def schedule_reminders(
    event_id: str,
    summary: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    participants: list[str],
    user_id: str,
) -> None:
    """
    Persist a meeting in the DB so the background checker will
    send reminders at 24 h and 15 min before the event.
    """
    async with async_session_factory() as session:
        meeting = ScheduledMeetingRow(
            user_id=user_id,
            event_id=event_id,
            summary=summary,
            description=description,
            start_time=start_time,
            end_time=end_time,
            participants=",".join(participants),
        )
        session.add(meeting)
        await session.commit()
        logger.info("Reminders scheduled for event %s at %s", event_id, start_time)


# ── Background checker (runs every 60 s) ─────────────────────


async def _check_and_send_reminders() -> None:
    """Scan upcoming meetings and send due reminders."""
    try:
        await _do_check_reminders()
    except Exception:
        logger.exception("Reminder check failed (will retry next cycle)")


async def _do_check_reminders() -> None:
    """Inner logic — separated so we can wrap with try/except."""
    # Use naive UTC (no tzinfo) because the DB column is TIMESTAMP WITHOUT TIME ZONE
    now = datetime.utcnow()

    async with async_session_factory() as session:
        result = await session.execute(
            select(ScheduledMeetingRow).where(
                ScheduledMeetingRow.start_time > now,
                ScheduledMeetingRow.start_time < now + timedelta(hours=25),
            )
        )
        meetings = list(result.scalars().all())

    for meeting in meetings:
        time_until = meeting.start_time - now

        # 24-hour reminder (send between 24h and 23h before)
        if (
            timedelta(hours=23) < time_until <= timedelta(hours=24)
            and not meeting.reminder_24h_sent
        ):
            await _send_reminder(meeting, reminder_type="24h")
            await _mark_sent(meeting.id, "reminder_24h_sent")

        # 10-minute reminder (send if we're between 8 and 12 minutes away)
        elif (
            timedelta(minutes=8) < time_until <= timedelta(minutes=12)
            and not meeting.reminder_15m_sent
        ):
            await _send_reminder(meeting, reminder_type="10m")
            await _mark_sent(meeting.id, "reminder_15m_sent")


# ── Reminder generation & dispatch ───────────────────────────


async def _generate_reminder_message(
    meeting: ScheduledMeetingRow,
    reminder_type: str,
) -> str:
    """Use Groq LLM to generate a context-aware reminder message."""
    time_label = "24 hours" if reminder_type == "24h" else "10 minutes"

    prompt = (
        f"Generate a brief, friendly meeting reminder. The meeting:\n"
        f"- Title: {meeting.summary}\n"
        f"- Description: {meeting.description}\n"
        f"- Starts at: {meeting.start_time.isoformat()}\n"
        f"- Participants: {meeting.participants}\n\n"
        f"This reminder is being sent {time_label} before the meeting.\n"
        f"Keep it concise (2-3 sentences) and professional."
    )

    response = await _groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )
    return response.choices[0].message.content or f"Reminder: {meeting.summary} starts in {time_label}."


async def _send_reminder(
    meeting: ScheduledMeetingRow,
    reminder_type: str,
) -> None:
    """Generate and send a reminder via both email and WhatsApp."""
    message = await _generate_reminder_message(meeting, reminder_type)
    participants = [p.strip() for p in meeting.participants.split(",") if p.strip()]
    time_label = "24 hours" if reminder_type == "24h" else "10 minutes"

    for participant in participants:
        is_phone = participant.startswith("+") or participant.lstrip("+").isdigit()
        is_email = "@" in participant

        # Email reminder
        if is_email:
            try:
                await send_email.ainvoke(
                    {
                        "to": participant,
                        "subject": f"\u23f0 Reminder: {meeting.summary} in {time_label}",
                        "body": message,
                    }
                )
            except Exception:
                logger.exception("Failed email reminder to %s for event %s", participant, meeting.event_id)

        # WhatsApp reminder
        if is_phone or is_email:
            try:
                await send_whatsapp.ainvoke(
                    {
                        "to": participant,
                        "message": f"\u23f0 {meeting.summary} in {time_label}\n{message}",
                    }
                )
            except Exception:
                logger.exception("Failed WhatsApp reminder to %s for event %s", participant, meeting.event_id)

    logger.info("Sent %s reminders for event %s to %d participants", reminder_type, meeting.event_id, len(participants))


async def _mark_sent(meeting_id: int, field: str) -> None:
    """Mark a reminder as sent in the database."""
    async with async_session_factory() as session:
        await session.execute(
            update(ScheduledMeetingRow)
            .where(ScheduledMeetingRow.id == meeting_id)
            .values(**{field: 1})
        )
        await session.commit()
