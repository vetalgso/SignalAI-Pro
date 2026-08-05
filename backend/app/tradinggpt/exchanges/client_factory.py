from __future__ import annotations

from typing import Any, Callable, Protocol

from .config import ExchangeExecutionSettings


class BinanceClientConstructor(Protocol):
    def __call__(
        self,
        api_key: str,
        api_secret: str,
        **kwargs: Any,
    ) -> object:
        """Construct a python-binance client."""


def _default_client_constructor() -> Callable[..., object]:
    from binance.client import Client

    return Client


def create_binance_client_from_credentials(
    *,
    api_key: str,
    secret_key: str,
    testnet: bool,
    client_constructor: BinanceClientConstructor | None = None,
) -> object:
    normalized_api_key = api_key.strip()
    normalized_secret_key = secret_key.strip()

    if not normalized_api_key:
        raise ValueError(
            "Binance API key is required."
        )

    if not normalized_secret_key:
        raise ValueError(
            "Binance secret key is required."
        )

    constructor = (
        client_constructor
        if client_constructor is not None
        else _default_client_constructor()
    )

    return constructor(
        normalized_api_key,
        normalized_secret_key,
        testnet=testnet,
    )


def create_binance_client(
    *,
    settings: ExchangeExecutionSettings,
    client_constructor: BinanceClientConstructor | None = None,
) -> object | None:
    if not settings.enable_binance_execution:
        return None

    settings.validate_binance_activation()

    api_key = settings.selected_api_key
    secret_key = settings.selected_secret_key

    if api_key is None or secret_key is None:
        raise RuntimeError(
            "Validated Binance credentials are unavailable."
        )

    return create_binance_client_from_credentials(
        api_key=api_key,
        secret_key=secret_key,
        testnet=settings.binance_testnet,
        client_constructor=client_constructor,
    )
