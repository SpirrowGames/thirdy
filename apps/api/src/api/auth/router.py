import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_schemas import UserRead

from api.auth.jwt import create_access_token, decode_access_token
from api.auth.oauth import oauth
from api.config import settings
from api.db.models import User
from api.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_login(request: Request):
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")

    # Upsert user
    result = await db.execute(
        select(User).where(User.google_sub == userinfo["sub"])
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=userinfo["email"],
            name=userinfo.get("name", ""),
            picture=userinfo.get("picture"),
            google_sub=userinfo["sub"],
        )
        db.add(user)
    else:
        user.email = userinfo["email"]
        user.name = userinfo.get("name", "")
        user.picture = userinfo.get("picture")

    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id)
    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={access_token}"
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Google Calendar incremental consent ---


@router.get("/google/calendar")
async def google_calendar_login(request: Request, token: str = Query(...)):
    """Start calendar OAuth flow. JWT passed as query param since browser redirect."""
    user_id = decode_access_token(token)
    if user_id is None:
        return RedirectResponse(
            url=f"{settings.frontend_url}/auth/calendar-callback?status=error&message=Invalid+token"
        )

    # Store user_id in session for the callback
    request.session["calendar_user_id"] = str(user_id)

    redirect_uri = str(request.url_for("google_calendar_callback"))
    return await oauth.google_calendar.authorize_redirect(
        request,
        redirect_uri,
        access_type="offline",
        prompt="consent",
    )


@router.get("/google/calendar/callback", name="google_calendar_callback")
async def google_calendar_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle calendar OAuth callback — save tokens to user."""
    user_id_str = request.session.pop("calendar_user_id", None)
    if not user_id_str:
        return RedirectResponse(
            url=f"{settings.frontend_url}/auth/calendar-callback?status=error&message=Session+expired"
        )

    try:
        token_data = await oauth.google_calendar.authorize_access_token(request)
    except Exception:
        logger.exception("Calendar OAuth token exchange failed")
        return RedirectResponse(
            url=f"{settings.frontend_url}/auth/calendar-callback?status=error&message=OAuth+failed"
        )

    from uuid import UUID

    result = await db.execute(select(User).where(User.id == UUID(user_id_str)))
    user = result.scalar_one_or_none()
    if user is None:
        return RedirectResponse(
            url=f"{settings.frontend_url}/auth/calendar-callback?status=error&message=User+not+found"
        )

    user.google_access_token = token_data.get("access_token")
    user.google_refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    user.google_token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in
    )

    await db.commit()

    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/calendar-callback?status=success"
    )


@router.get("/google/calendar/status")
async def google_calendar_status(current_user: User = Depends(get_current_user)):
    """Check if the current user has Google Calendar connected."""
    return {"connected": current_user.google_refresh_token is not None}


@router.post("/google/calendar/disconnect")
async def google_calendar_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect Google Calendar by clearing stored tokens."""
    current_user.google_access_token = None
    current_user.google_refresh_token = None
    current_user.google_token_expires_at = None
    await db.commit()
    return {"connected": False}
