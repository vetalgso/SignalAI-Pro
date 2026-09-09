from __future__ import annotations

from typing import Any

import pytest

from app.tradinggpt.exchanges import (
    ExchangeAdapterRegistry,
    ExchangeExecutionSettings,
    create_binance_client,
)


class FakeBinanceClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.kwargs = kwargs


def test_settings_default_to_safe_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = [
        "ENABLE_BINANCE_EXECUTION",
        "BINANCE_TESTNET",
        "ENABLE_REAL_TRADING",
        "BINANCE_API_KEY",
        "BINANCE_SECRET_KEY",
        "BINANCE_TESTNET_API_KEY",
        "BINANCE_TESTNET_SECRET_KEY",
    ]

    for name in names:
        monkeypatch.delenv(name, raising=False)

    settings = ExchangeExecutionSettings.from_env()

    assert settings.enable_binance_execution is False
    assert settings.binance_testnet is True
    assert settings.enable_real_trading is False
    assert settings.has_selected_credentials is False


def test_disabled_binance_returns_no_client() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=False,
    )

    client = create_binance_client(
        settings=settings,
        client_constructor=FakeBinanceClient,
    )

    assert client is None


def test_testnet_client_uses_testnet_credentials() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
        enable_real_trading=False,
        binance_testnet_api_key="test-key",
        binance_testnet_secret_key="test-secret",
    )

    client = create_binance_client(
        settings=settings,
        client_constructor=FakeBinanceClient,
    )

    assert isinstance(client, FakeBinanceClient)
    assert client.api_key == "test-key"
    assert client.api_secret == "test-secret"
    assert client.kwargs["testnet"] is True


def test_live_client_requires_real_trading_switch() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=False,
        enable_real_trading=False,
        binance_api_key="live-key",
        binance_secret_key="live-secret",
    )

    with pytest.raises(
        ValueError,
        match="ENABLE_REAL_TRADING",
    ):
        create_binance_client(
            settings=settings,
            client_constructor=FakeBinanceClient,
        )


def test_missing_selected_credentials_are_rejected() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
    )

    with pytest.raises(
        ValueError,
        match="credentials are missing",
    ):
        settings.validate_binance_activation()


def test_registry_contains_only_paper_by_default() -> None:
    settings = ExchangeExecutionSettings()

    service = ExchangeAdapterRegistry(
        settings=settings
    ).build_execution_service()

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is False


def test_registry_registers_binance_testnet() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
        binance_testnet_api_key="test-key",
        binance_testnet_secret_key="test-secret",
    )

    fake_client = object()

    registry = ExchangeAdapterRegistry(
        settings=settings,
        binance_client_factory=lambda _: fake_client,
    )

    service = registry.build_execution_service()

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is True


def test_registry_rejects_live_without_safety_switch() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=False,
        enable_real_trading=False,
        binance_api_key="live-key",
        binance_secret_key="live-secret",
    )

    registry = ExchangeAdapterRegistry(
        settings=settings,
        binance_client_factory=lambda _: object(),
    )

    with pytest.raises(
        ValueError,
        match="ENABLE_REAL_TRADING",
    ):
        registry.build_execution_service()


def test_registry_rejects_none_client() -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
        binance_testnet_api_key="test-key",
        binance_testnet_secret_key="test-secret",
    )

    registry = ExchangeAdapterRegistry(
        settings=settings,
        binance_client_factory=lambda _: None,
    )

    with pytest.raises(
        RuntimeError,
        match="returned no client",
    ):
        registry.build_execution_service()
