import os
from functools import lru_cache

from pydantic import Field, model_validator
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

    order_reconciliation_background_enabled: bool = False
    order_reconciliation_poll_seconds: float = Field(
        default=15.0,
        gt=0,
        le=3600,
    )
    order_reconciliation_batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
    )
    order_reconciliation_history_limit: int = Field(
        default=100_000,
        ge=100,
        le=10_000_000,
    )
    order_reconciliation_advisory_lock_key: int = Field(
        default=2026082101,
        ge=1,
        le=9223372036854775807,
    )

    signal_tracking_enabled: bool = True
    signal_tracking_interval_seconds: float = Field(
        default=60.0,
        ge=10,
        le=3600,
    )

    signal_scanner_background_enabled: bool = False
    signal_scanner_interval_seconds: float = Field(
        default=900.0,
        ge=60,
        le=86400,
    )
    signal_scanner_risk_level: str = "medium"
    signal_scanner_market_limit: int = Field(
        default=30,
        ge=1,
        le=100,
    )
    signal_scanner_min_confidence: float = Field(
        default=60.0,
        ge=0,
        le=100,
    )
    signal_scanner_advisory_lock_key: int = Field(
        default=2026082801,
        ge=1,
        le=9223372036854775807,
    )

    signal_ai_review_enabled: bool = False
    signal_ai_provider: str = "openai"
    signal_ai_base_url: str = "https://api.openai.com/v1"
    signal_ai_model: str = "gpt-5-mini"
    signal_ai_api_key: str = ""
    signal_ai_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=120,
    )
    signal_ai_max_candidates: int = Field(
        default=3,
        ge=1,
        le=10,
    )
    signal_ai_min_confidence: float = Field(
        default=60.0,
        ge=0,
        le=100,
    )
    signal_ai_min_verdict_confidence: float = Field(
        default=60.0,
        ge=0,
        le=100,
    )
    signal_ai_min_ranking_score: float = Field(
        default=65.0,
        ge=0,
        le=100,
    )
    signal_ai_min_consensus_score: float = Field(
        default=90.0,
        ge=0,
        le=100,
    )
    signal_ai_min_timeframe_score: float = Field(
        default=90.0,
        ge=0,
        le=100,
    )
    signal_ai_max_quality_penalty: int = Field(
        default=10,
        ge=0,
        le=100,
    )
    signal_ai_max_candidate_age_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
    )

    signal_ai_min_stop_distance_percent: float = Field(
        default=0.25,
        ge=0,
        le=100,
    )
    signal_ai_min_target_distance_percent: float = Field(
        default=0.50,
        ge=0,
        le=100,
    )
    signal_ai_min_risk_reward_ratio: float = Field(
        default=1.5,
        ge=1,
        le=10,
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

    testnet_order_execution_enabled: bool = True
    testnet_max_order_notional: float = Field(
        default=100.0,
        gt=0,
        le=1_000_000_000,
    )
    testnet_max_daily_notional: float = Field(
        default=500.0,
        gt=0,
        le=1_000_000_000,
    )
    testnet_max_open_orders: int = Field(
        default=5,
        ge=1,
        le=1_000,
    )
    testnet_allowed_symbols: str = ""

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True
    binance_market_base_url: str = "https://api.binance.com"
    binance_request_timeout_seconds: float = 10.0
    telegram_bot_token: str = ""

    telegram_signal_enabled: bool = False
    telegram_signal_bot_token: str = ""
    telegram_signal_chat_id: str = ""
    telegram_signal_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
    )
    telegram_signal_dispatch_poll_seconds: float = Field(
        default=10.0,
        gt=0,
        le=3600,
    )
    telegram_signal_batch_size: int = Field(
        default=20,
        ge=1,
        le=500,
    )
    telegram_signal_max_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    telegram_signal_retry_base_seconds: float = Field(
        default=30.0,
        gt=0,
        le=3600,
    )
    telegram_signal_processing_lease_seconds: float = Field(
        default=300.0,
        gt=0,
        le=86400,
    )
    telegram_signal_advisory_lock_key: int = Field(
        default=2026082701,
        ge=1,
        le=9223372036854775807,
    )

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


    @model_validator(mode="after")
    def validate_production_safety(
        self,
    ) -> "Settings":
        environment = (
            self.environment
            .strip()
            .lower()
        )

        if environment not in {
            "production",
            "prod",
        }:
            return self

        errors: list[str] = []

        def is_placeholder(
            value: str,
        ) -> bool:
            normalized = value.strip().lower()

            return (
                not normalized
                or any(
                    marker in normalized
                    for marker in (
                        "change-me",
                        "replace",
                        "placeholder",
                        "example",
                    )
                )
            )

        if self.debug:
            errors.append(
                "DEBUG must be false"
            )

        if (
            is_placeholder(
                self.jwt_secret_key
            )
            or len(
                self.jwt_secret_key
            ) < 32
        ):
            errors.append(
                "JWT_SECRET_KEY must be "
                "a strong secret"
            )

        if (
            is_placeholder(
                self.database_url
            )
            or "signalai:signalai@" in (
                self.database_url
            )
            or self.database_url.startswith(
                "sqlite"
            )
        ):
            errors.append(
                "DATABASE_URL must use "
                "production credentials"
            )

        encryption_key = (
            self
            .exchange_credentials_encryption_key
        )

        if (
            is_placeholder(encryption_key)
            or len(encryption_key) < 32
        ):
            errors.append(
                "EXCHANGE_CREDENTIALS_"
                "ENCRYPTION_KEY must be set"
            )

        if (
            self.signal_ai_review_enabled
            and (
                self.signal_ai_provider.strip().lower()
                != "openai"
                or is_placeholder(
                    self.signal_ai_api_key
                )
                or not self.signal_ai_api_key.startswith(
                    "sk-"
                )
            )
        ):
            errors.append(
                "A valid SIGNAL_AI_API_KEY is "
                "required when AI Review is enabled"
            )

        if (
            self.telegram_signal_enabled
            and (
                not self
                .telegram_signal_bot_token
                .strip()
                or not self
                .telegram_signal_chat_id
                .strip()
            )
        ):
            errors.append(
                "Telegram destination is "
                "required when publisher "
                "is enabled"
            )

        if errors:
            raise ValueError(
                "Unsafe production "
                "configuration: "
                + "; ".join(errors)
            )

        return self

    model_config = SettingsConfigDict(
        env_file=(
            ".env"
            if os.access(".env", os.R_OK)
            else None
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
