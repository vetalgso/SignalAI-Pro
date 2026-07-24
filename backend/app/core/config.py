from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalAI Pro"
    app_version: str = "0.2.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://signalai:signalai@db:5432/signalai"
    redis_url: str = "redis://redis:6379/0"

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True
    telegram_bot_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
