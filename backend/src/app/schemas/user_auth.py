from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class UserAuthReadyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    login_available: bool
    detail: str | None = None
    jwt_configured: bool | None = None
    google_configured: bool | None = None
    email_login_available: bool | None = None
    app_users_table_reachable: bool | None = None


class UserSessionResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None = None
    picture_url: str | None = None
    token_expires_at: str | None = None
    token_ttl_minutes: int | None = None
    seconds_until_expiry: int | None = None


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido.")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return v


class UserLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()
