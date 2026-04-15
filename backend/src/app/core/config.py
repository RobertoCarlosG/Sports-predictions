from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
