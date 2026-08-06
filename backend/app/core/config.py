from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalAI Pro"
    app_version: str = "0.6.0"
    environment: str = "development"
    debug: bool = True

    scheduler_background_loop_enabled: bool = True
    scheduler_background_poll_seconds: float = Field(
        default=5.0,
        gt=0,
        le=3600,
    )

    signal_tracking_enabled: bool = True
    signal_tracking_interval_seconds: float = Field(
        default=60.0,
        ge=10,
        le=3600,
    )

    scheduler_distributed_lock_enabled: bool = True
    scheduler_advisory_lock_key: int = Field(
        default=2026080320,
        ge=1,
        le=9223372036854775807,
    )

    database_url: str = "postgresql+psycopg2://signalai:signalai@db:5432/signalai"
    redis_url: str = "redis://redis:6379/0"
    exchange_credentials_encryption_key: str = ""

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True
    binance_market_base_url: str = "https://api.binance.com"
    binance_request_timeout_seconds: float = 10.0
    telegram_bot_token: str = ""

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

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
