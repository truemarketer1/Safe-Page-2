"""Env-driven settings loaded via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/crm"
    api_auth_token: str = "dev-insecure-token"

    # Webhook signing secrets (each provider has its own scheme)
    stripe_webhook_secret: str = ""
    meta_app_secret: str = ""
    cal_webhook_secret: str = ""
    retell_webhook_secret: str = ""
    manychat_webhook_secret: str = ""

    # Internal
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
