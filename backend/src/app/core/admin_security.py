from __future__ import annotations

import datetime as dt

import bcrypt
import jwt

# Límite de bcrypt; por encima habría que pre-hashear (p. ej. SHA-256) — no lo hacemos en MVP.
_BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")
    if len(pw) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"La contraseña no puede superar {_BCRYPT_MAX_PASSWORD_BYTES} bytes (límite de bcrypt).",
        )
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(*, secret: str, subject: str, expire_minutes: int) -> str:
    now = dt.datetime.now(dt.UTC)
    exp = now + dt.timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "iat": now, "exp": exp}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise jwt.InvalidTokenError("missing sub")
    return sub


def decode_token_expires_at_utc(token: str, secret: str) -> dt.datetime | None:
    """Lee ``exp`` del JWT sin volver a firmar (misma clave que decode_access_token)."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        ts = payload.get("exp")
        if ts is None:
            return None
        return dt.datetime.fromtimestamp(int(ts), tz=dt.UTC)
    except jwt.PyJWTError:
        return None
