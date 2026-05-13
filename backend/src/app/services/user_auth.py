"""Persistencia de usuarios OAuth (Google)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bets import AppUser


async def upsert_app_user_from_google_profile(
    session: AsyncSession,
    *,
    google_id: str,
    email: str,
    display_name: str | None,
    picture_url: str | None,
) -> AppUser:
    now = dt.datetime.now(dt.UTC)
    result = await session.execute(select(AppUser).where(AppUser.google_id == google_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = AppUser(
            google_id=google_id,
            email=email,
            display_name=display_name,
            picture_url=picture_url,
            last_login_at=now,
        )
        session.add(user)
        await session.flush()
        return user

    user.email = email
    user.display_name = display_name
    user.picture_url = picture_url
    user.last_login_at = now
    user.is_active = True
    await session.flush()
    return user


async def get_app_user(session: AsyncSession, user_id: uuid.UUID) -> AppUser | None:
    return await session.get(AppUser, user_id)
