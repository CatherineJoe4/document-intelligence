from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Intelligence API"
    app_env: str = "development"
    log_level: str = "INFO"

    gemini_api_key: str
    gemini_model: str = "gemini-3.6-flash"

    database_url: str = "sqlite:///./document_intelligence.db"

    max_file_size_mb: int = 10
    max_pages: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()