from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_schemas import UserRead

from api.auth.jwt import create_access_token
from api.auth.oauth import oauth
from api.config import settings
from api.db.models import User
from api.dependencies import get_current_user, get_db

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
