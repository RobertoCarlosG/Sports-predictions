from __future__ import annotations

import datetime as dt

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    return pwd_context.verify(plain, password_hash)


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
