from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models import User

logger = logging.getLogger(__name__)

PRESET_DURATIONS: dict[str, int] = {
    "quick_sync": 15,
    "discussion": 30,
    "deep_dive": 60,
}

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


async def refresh_token_if_needed(user: User, db: AsyncSession) -> str:
    """Return a valid access token, refreshing if expired."""
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")

    now = datetime.now(timezone.utc)

    # If token is still valid, return it
    if (
        user.google_access_token
        and user.google_token_expires_at
        and user.google_token_expires_at > now + timedelta(minutes=1)
    ):
        return user.google_access_token

    # Refresh the token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code != 200:
        logger.warning("Google token refresh failed: %s", resp.text)
        # Clear tokens — user must re-connect
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_token_expires_at = None
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Google Calendar token expired. Please reconnect.",
        )

    data = resp.json()
    user.google_access_token = data["access_token"]
    user.google_token_expires_at = now + timedelta(seconds=data.get("expires_in", 3600))
    # Google may return a new refresh token
    if "refresh_token" in data:
        user.google_refresh_token = data["refresh_token"]
    await db.commit()

    return user.google_access_token


async def create_event(
    user: User,
    db: AsyncSession,
    summary: str,
    description: str,
    start: datetime,
    duration_minutes: int,
    attendees: list[str],
) -> dict:
    """Create a Google Calendar event. Returns the API response body."""
    access_token = await refresh_token_if_needed(user, db)

    end = start + timedelta(minutes=duration_minutes)

    event_body: dict = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "UTC",
        },
    }

    if attendees:
        event_body["attendees"] = [{"email": email} for email in attendees]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            CALENDAR_EVENTS_URL,
            json=event_body,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"sendUpdates": "all"},
        )

    if resp.status_code == 401:
        # Token was revoked between refresh check and API call
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_token_expires_at = None
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Google Calendar token revoked. Please reconnect.",
        )

    if resp.status_code not in (200, 201):
        logger.error("Google Calendar API error: %s %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=502,
            detail="Failed to create Google Calendar event",
        )

    return resp.json()
