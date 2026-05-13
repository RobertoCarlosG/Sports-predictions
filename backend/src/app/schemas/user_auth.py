from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserAuthReadyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    login_available: bool
    detail: str | None = None
    jwt_configured: bool | None = None
    google_configured: bool | None = None
    app_users_table_reachable: bool | None = None


class UserSessionResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None = None
    picture_url: str | None = None
    token_expires_at: str | None = None
    token_ttl_minutes: int | None = None
    seconds_until_expiry: int | None = None
