from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.config import settings


def _token_from_request(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(settings.admin_cookie_name)


async def require_admin_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not settings.admin_jwt_secret.strip():
        raise HTTPException(
            status_code=503,
            detail="Acceso administrativo no configurado (ADMIN_JWT_SECRET).",
        )
    token = _token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Se requiere autenticación.")
    try:
        from app.core.admin_security import decode_access_token

        return decode_access_token(token, settings.admin_jwt_secret)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada.") from e


AdminUserDep = Annotated[str, Depends(require_admin_token)]
