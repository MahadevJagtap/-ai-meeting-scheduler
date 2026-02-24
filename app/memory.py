"""
Memory layer for user preferences.

Switched from pgvector to simple text-based retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import UserPreferenceRow, async_session_factory

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────


async def embed_preference(user_id: str, preference_text: str) -> UserPreferenceRow:
    """Store a user scheduling preference."""
    row = UserPreferenceRow(
        user_id=user_id,
        preference_text=preference_text,
        created_at=datetime.now(timezone.utc),
    )

    async with async_session_factory() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        logger.info("Stored preference id=%s for user=%s", row.id, user_id)
        return row


async def retrieve_relevant_preferences(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[str]:
    """
    Retrieve all user preferences for a given user.
    (Simplified from pgvector search).
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserPreferenceRow.preference_text)
            .where(UserPreferenceRow.user_id == user_id)
            .limit(top_k)
        )
        preferences = [row[0] for row in result.fetchall()]

    logger.info(
        "Retrieved %d preferences for user=%s",
        len(preferences),
        user_id,
    )
    return preferences


async def get_all_preferences(user_id: str) -> list[UserPreferenceRow]:
    """Return all stored preferences for a user."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserPreferenceRow)
            .where(UserPreferenceRow.user_id == user_id)
            .order_by(UserPreferenceRow.created_at.desc())
        )
        return list(result.scalars().all())


async def delete_preference(preference_id: int) -> bool:
    """Delete a preference by its primary key. Returns True if found."""
    async with async_session_factory() as session:
        row = await session.get(UserPreferenceRow, preference_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True
