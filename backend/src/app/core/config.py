from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    """Render/Supabase suelen dar postgresql://… sin driver; async requiere +asyncpg."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/sports_predictions"
    cors_origins: str = "http://localhost:4200"
    mlb_api_base_url: str = "https://statsapi.mlb.com/api/v1"
    # Límite global MLB: tras N peticiones, pausa (0 = desactivado).
    mlb_api_rate_limit_burst_size: int = 5
    mlb_api_rate_limit_cooldown_seconds: float = 25.0
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    # Path to bundled stadium coordinates (JSON) relative to cwd or absolute
    mlb_stadiums_path: str = "src/app/data/mlb_stadiums.json"
    # Path to trained model (joblib); empty = package default under app/ml/artifacts/
    ml_model_path: str = ""
    # Si True y no hay archivo, arranca entrenando modelo sintético (no recomendado en prod).
    ml_auto_synthetic_on_missing: bool = False
    # Si True, tras sync/listado MLB se precalcula caché de predicciones (por defecto manual vía admin).
    pipeline_auto_cache_predictions: bool = False
    # Secreto HS256 para JWT del panel admin (mín. 16 caracteres en prod). Vacío = login deshabilitado.
    admin_jwt_secret: str = ""
    admin_token_expire_minutes: int = 120
    # Cookie HttpOnly para el JWT del panel (nombre distinto del doc genérico access_token para evitar colisiones).
    admin_cookie_name: str = "sp_admin_access"
    # lax = mismo sitio; none + secure para front y API en dominios distintos (p. ej. Vercel + Render).
    admin_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_cookie_secure: bool = False
    admin_cookie_domain: str | None = None
    # Exponer trazas/mensajes técnicos en JSON de error (solo desarrollo)
    debug: bool = False
    # Solo si DATABASE_URL apunta a un host con IPv4 (p. ej. add-on IPv4 Supabase). Free tier + direct 5432
    # suele ser IPv6-only: ahí usa transaction pooler; esta opción no arregla la falta de IPv4 en directo.
    database_force_ipv4: bool = False

    @model_validator(mode="after")
    def _normalize_database_url(self) -> Self:
        self.database_url = normalize_async_database_url(self.database_url)
        if self.admin_cookie_domain == "":
            self.admin_cookie_domain = None
        return self


settings = Settings()
