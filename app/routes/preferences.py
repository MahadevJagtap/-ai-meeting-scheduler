"""
FastAPI routes for user preference CRUD operations.

Endpoints:
  POST   /api/preferences       – Add a new preference (embeds & stores)
  GET    /api/preferences/{uid} – List all preferences for a user
  DELETE /api/preferences/{id}  – Delete a preference by ID
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from app.memory import delete_preference, embed_preference, get_all_preferences
from app.models import UserPreferenceCreate, UserPreferenceOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["preferences"])


@router.post("/preferences", response_model=UserPreferenceOut, status_code=201)
async def create_preference(payload: UserPreferenceCreate) -> UserPreferenceOut:
    """Embed and store a new user scheduling preference."""
    try:
        row = await embed_preference(
            user_id=payload.user_id,
            preference_text=payload.preference_text,
        )
        return UserPreferenceOut.model_validate(row)
    except Exception as exc:
        logger.exception("Failed to create preference")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/preferences/{user_id}", response_model=list[UserPreferenceOut])
async def list_preferences(user_id: str) -> list[UserPreferenceOut]:
    """Return all stored preferences for a given user."""
    rows = await get_all_preferences(user_id)
    return [UserPreferenceOut.model_validate(r) for r in rows]


@router.delete("/preferences/{preference_id}", status_code=204, response_class=Response)
async def remove_preference(preference_id: int) -> Response:
    """Delete a preference by its primary key."""
    deleted = await delete_preference(preference_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference not found")
    return Response(status_code=204)
