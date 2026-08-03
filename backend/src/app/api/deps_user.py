from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.config import settings


def user_token_from_request(request: Request, authorization: str | None = None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(settings.user_cookie_name)


async def require_user_id(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    if not settings.user_jwt_secret.strip():
        raise HTTPException(
            status_code=503,
            detail="Sesión de usuario no configurada (USER_JWT_SECRET).",
        )
    token = user_token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Se requiere iniciar sesión.")

    is_cookie = authorization is None or not authorization.lower().startswith("bearer ")
    if is_cookie and request.method not in ["GET", "HEAD", "OPTIONS"]:
        xrw = request.headers.get("x-requested-with")
        if not xrw or xrw.lower() != "xmlhttprequest":
            raise HTTPException(status_code=403, detail="Falta cabecera X-Requested-With para prevenir CSRF.")

    try:
        from app.core.admin_security import decode_access_token

        sub = decode_access_token(token, settings.user_jwt_secret)
        return uuid.UUID(sub)
    except (jwt.PyJWTError, ValueError) as e:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada.") from e


UserIdDep = Annotated[uuid.UUID, Depends(require_user_id)]
