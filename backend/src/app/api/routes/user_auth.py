"""OAuth Google + sesión HttpOnly para usuarios del control de apuestas."""

from __future__ import annotations

import datetime as dt
import logging
import secrets
import urllib.parse
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_security import create_access_token, decode_access_token, decode_token_expires_at_utc
from app.core.config import settings
from app.db.session import get_db
from app.models.bets import AppUser
from app.api.deps_user import user_token_from_request
from app.schemas.user_auth import UserAuthReadyResponse, UserSessionResponse
from app.services.user_auth import get_app_user, upsert_app_user_from_google_profile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"


def _user_oauth_configured() -> bool:
    return bool(
        settings.user_jwt_secret.strip()
        and settings.google_client_id.strip()
        and settings.google_client_secret.strip()
        and settings.google_redirect_uri.strip(),
    )


def _set_user_session_cookie(response: Response, token: str) -> None:
    kwargs: dict = {
        "key": settings.user_cookie_name,
        "value": token,
        "httponly": True,
        "secure": settings.user_cookie_secure,
        "samesite": settings.user_cookie_samesite,
        "max_age": settings.user_token_expire_minutes * 60,
        "path": "/",
    }
    if settings.user_cookie_domain:
        kwargs["domain"] = settings.user_cookie_domain
    response.set_cookie(**kwargs)


def _clear_user_session_cookie(response: Response) -> None:
    kwargs: dict = {
        "key": settings.user_cookie_name,
        "path": "/",
        "httponly": True,
        "secure": settings.user_cookie_secure,
        "samesite": settings.user_cookie_samesite,
    }
    if settings.user_cookie_domain:
        kwargs["domain"] = settings.user_cookie_domain
    response.delete_cookie(**kwargs)


def _set_oauth_state_cookie(response: Response, state: str) -> None:
    kwargs: dict = {
        "key": settings.oauth_state_cookie_name,
        "value": state,
        "httponly": True,
        "secure": settings.user_cookie_secure,
        "samesite": settings.user_cookie_samesite,
        "max_age": 600,
        "path": "/",
    }
    if settings.user_cookie_domain:
        kwargs["domain"] = settings.user_cookie_domain
    response.set_cookie(**kwargs)


def _clear_oauth_state_cookie(response: Response) -> None:
    kwargs: dict = {
        "key": settings.oauth_state_cookie_name,
        "path": "/",
        "httponly": True,
        "secure": settings.user_cookie_secure,
        "samesite": settings.user_cookie_samesite,
    }
    if settings.user_cookie_domain:
        kwargs["domain"] = settings.user_cookie_domain
    response.delete_cookie(**kwargs)


def _session_response(user: AppUser, request: Request) -> UserSessionResponse:
    token = user_token_from_request(request, None)
    exp = decode_token_expires_at_utc(token, settings.user_jwt_secret) if token else None
    now = dt.datetime.now(dt.UTC)
    sec = int((exp - now).total_seconds()) if exp else None
    exp_s = exp.replace(microsecond=0).isoformat().replace("+00:00", "Z") if exp else None
    return UserSessionResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        picture_url=user.picture_url,
        token_expires_at=exp_s,
        token_ttl_minutes=settings.user_token_expire_minutes,
        seconds_until_expiry=sec,
    )


@router.get("/ready", response_model=UserAuthReadyResponse)
async def user_auth_ready(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserAuthReadyResponse:
    jwt_ok = bool(settings.user_jwt_secret.strip())
    google_ok = bool(
        settings.google_client_id.strip()
        and settings.google_client_secret.strip()
        and settings.google_redirect_uri.strip(),
    )
    table_ok = False
    table_hint: str | None = None
    try:
        await session.execute(select(AppUser.id).limit(1))
        table_ok = True
    except ProgrammingError:
        table_hint = (
            "Falta la tabla app_users. Ejecuta `backend/sql/007_app_users_and_bets.sql` en la base de datos."
        )
    except SQLAlchemyError as e:
        log.warning("user auth/ready DB check: %s", e)
        table_hint = "No se pudo consultar app_users."

    login_ok = jwt_ok and google_ok and table_ok
    parts: list[str] = []
    if not jwt_ok:
        parts.append("USER_JWT_SECRET no está definido o está vacío.")
    if not google_ok:
        parts.append("Configura GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REDIRECT_URI.")
    if not table_ok and table_hint:
        parts.append(table_hint)
    detail = "\n\n".join(parts) if parts else None
    return UserAuthReadyResponse(
        login_available=login_ok,
        detail=detail,
        jwt_configured=jwt_ok,
        google_configured=google_ok,
        app_users_table_reachable=table_ok,
    )


@router.get("/google")
async def google_oauth_start() -> RedirectResponse:
    if not _user_oauth_configured():
        raise HTTPException(status_code=503, detail="OAuth de Google no está configurado en el servidor.")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id.strip(),
        "redirect_uri": settings.google_redirect_uri.strip(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"{_GOOGLE_AUTH}?{urllib.parse.urlencode(params)}"
    response = RedirectResponse(url=url, status_code=302)
    _set_oauth_state_cookie(response, state)
    return response


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    if not _user_oauth_configured():
        raise HTTPException(status_code=503, detail="OAuth de Google no está configurado en el servidor.")
    if error:
        log.warning("Google OAuth error param: %s", error)
        return RedirectResponse(
            url=f"{settings.oauth_post_login_redirect}?login_error=1",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Faltan parámetros de autorización.")

    cookie_state = request.cookies.get(settings.oauth_state_cookie_name)
    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido. Vuelve a intentar el inicio de sesión.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id.strip(),
                "client_secret": settings.google_client_secret.strip(),
                "redirect_uri": settings.google_redirect_uri.strip(),
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            log.warning("Google token exchange failed: %s %s", token_resp.status_code, token_resp.text[:500])
            raise HTTPException(status_code=502, detail="No se pudo completar el inicio de sesión con Google.")
        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(status_code=502, detail="Respuesta de token inválida.")

        ui = await client.get(
            _GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if ui.status_code != 200:
            log.warning("Google userinfo failed: %s", ui.status_code)
            raise HTTPException(status_code=502, detail="No se pudo leer el perfil de Google.")
        profile = ui.json()

    google_id = str(profile.get("id") or "").strip()
    email = str(profile.get("email") or "").strip()
    if not google_id or not email:
        raise HTTPException(status_code=502, detail="Perfil de Google incompleto (falta id o email).")

    display_name = profile.get("name")
    if display_name is not None:
        display_name = str(display_name).strip() or None
    picture = profile.get("picture")
    picture_url = str(picture).strip() if isinstance(picture, str) and picture.strip() else None

    user = await upsert_app_user_from_google_profile(
        session,
        google_id=google_id,
        email=email,
        display_name=display_name,
        picture_url=picture_url,
    )
    await session.commit()

    jwt = create_access_token(
        secret=settings.user_jwt_secret,
        subject=str(user.id),
        expire_minutes=settings.user_token_expire_minutes,
    )
    response = RedirectResponse(url=settings.oauth_post_login_redirect, status_code=302)
    _clear_oauth_state_cookie(response)
    _set_user_session_cookie(response, jwt)
    return response


@router.get("/me", response_model=UserSessionResponse)
async def user_me(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSessionResponse:
    if not settings.user_jwt_secret.strip():
        raise HTTPException(status_code=503, detail="Sesión de usuario no configurada.")
    token = user_token_from_request(request, None)
    if not token:
        raise HTTPException(status_code=401, detail="No hay sesión activa.")
    try:
        sub = decode_access_token(token, settings.user_jwt_secret)
        uid = uuid.UUID(sub)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Sesión no válida.") from e

    user = await get_app_user(session, uid)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return _session_response(user, request)


@router.post("/logout")
async def user_logout(response: Response) -> dict[str, str]:
    _clear_user_session_cookie(response)
    return {"message": "Sesión cerrada", "detail": ""}
