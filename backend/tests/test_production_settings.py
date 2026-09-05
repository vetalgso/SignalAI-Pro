import pytest
from pydantic import ValidationError

from app.core.config import Settings


SAFE = {
    "environment": "production",
    "debug": False,
    "database_url": (
        "postgresql+psycopg2://"
        "signalai:9f4e5a6b7c8d@"
        "db:5432/signalai"
    ),
    "jwt_secret_key": "j" * 64,
    (
        "exchange_credentials_"
        "encryption_key"
    ): "e" * 44,
    "telegram_signal_enabled": False,
}


def production(
    **overrides: object,
) -> Settings:
    return Settings(
        _env_file=None,
        **{
            **SAFE,
            **overrides,
        },
    )


def test_safe_production_settings() -> None:
    settings = production()

    assert settings.environment == "production"
    assert settings.debug is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"debug": True},
            "DEBUG must be false",
        ),
        (
            {
                "jwt_secret_key":
                    "change-me-in-production"
            },
            "JWT_SECRET_KEY",
        ),
        (
            {
                "database_url": (
                    "postgresql+psycopg2://"
                    "signalai:signalai@"
                    "db:5432/signalai"
                )
            },
            "DATABASE_URL",
        ),
        (
            {
                (
                    "exchange_credentials_"
                    "encryption_key"
                ): ""
            },
            (
                "EXCHANGE_CREDENTIALS_"
                "ENCRYPTION_KEY"
            ),
        ),
    ],
)
def test_unsafe_production_rejected(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=message,
    ):
        production(**overrides)


def test_enabled_telegram_requires_destination(
) -> None:
    with pytest.raises(
        ValidationError,
        match="Telegram destination",
    ):
        production(
            telegram_signal_enabled=True,
            telegram_signal_bot_token="",
            telegram_signal_chat_id="",
        )


def test_development_defaults_still_work(
) -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
    )

    assert settings.environment == "development"
