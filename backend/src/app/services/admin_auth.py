"""
Autenticación del panel de operaciones (tabla admin_users).

El JWT se entrega al cliente en una cookie HttpOnly desde la ruta HTTP de login;
este módulo solo valida credenciales y genera el token. Ver docs/HTTPONLY_AUTH.md.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_security import create_access_token, verify_password
from app.core.config import settings
from app.models.mlb import AdminUser


class AdminAuthError(Exception):
    """Credenciales inválidas o usuario inactivo."""


async def login_with_password(
    username: str,
    password: str,
    db: AsyncSession,
) -> tuple[str, str]:
    """
    Valida usuario y contraseña contra admin_users.

    Returns:
        (username, jwt) para que la capa HTTP fije la cookie y devuelva el perfil sin el token.
    """
    if not settings.admin_jwt_secret.strip():
        raise AdminAuthError("Servidor sin ADMIN_JWT_SECRET.")

    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AdminAuthError("Usuario o contraseña incorrectos.")

    token = create_access_token(
        secret=settings.admin_jwt_secret,
        subject=user.username,
        expire_minutes=settings.admin_token_expire_minutes,
    )
    return user.username, token
