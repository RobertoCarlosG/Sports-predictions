from typing import Self

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
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    # Path to bundled stadium coordinates (JSON) relative to cwd or absolute
    mlb_stadiums_path: str = "src/app/data/mlb_stadiums.json"
    # Path to trained model (joblib); empty = package default under app/ml/artifacts/
    ml_model_path: str = ""
    # Exponer trazas/mensajes técnicos en JSON de error (solo desarrollo)
    debug: bool = False

    @model_validator(mode="after")
    def _normalize_database_url(self) -> Self:
        self.database_url = normalize_async_database_url(self.database_url)
        return self


settings = Settings()
