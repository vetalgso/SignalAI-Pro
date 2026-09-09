from __future__ import annotations

from dataclasses import dataclass
import os


_TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
}


def _read_bool(
    name: str,
    *,
    default: bool = False,
) -> bool:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in _TRUE_VALUES


def _read_optional_string(
    name: str,
) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


@dataclass(frozen=True, slots=True)
class ExchangeExecutionSettings:
    enable_binance_execution: bool = False
    binance_testnet: bool = True
    enable_real_trading: bool = False

    binance_api_key: str | None = None
    binance_secret_key: str | None = None

    binance_testnet_api_key: str | None = None
    binance_testnet_secret_key: str | None = None

    @classmethod
    def from_env(
        cls,
    ) -> "ExchangeExecutionSettings":
        return cls(
            enable_binance_execution=_read_bool(
                "ENABLE_BINANCE_EXECUTION",
                default=False,
            ),
            binance_testnet=_read_bool(
                "BINANCE_TESTNET",
                default=True,
            ),
            enable_real_trading=_read_bool(
                "ENABLE_REAL_TRADING",
                default=False,
            ),
            binance_api_key=_read_optional_string(
                "BINANCE_API_KEY"
            ),
            binance_secret_key=_read_optional_string(
                "BINANCE_SECRET_KEY"
            ),
            binance_testnet_api_key=_read_optional_string(
                "BINANCE_TESTNET_API_KEY"
            ),
            binance_testnet_secret_key=_read_optional_string(
                "BINANCE_TESTNET_SECRET_KEY"
            ),
        )

    @property
    def selected_api_key(
        self,
    ) -> str | None:
        if self.binance_testnet:
            return self.binance_testnet_api_key

        return self.binance_api_key

    @property
    def selected_secret_key(
        self,
    ) -> str | None:
        if self.binance_testnet:
            return self.binance_testnet_secret_key

        return self.binance_secret_key

    @property
    def has_selected_credentials(
        self,
    ) -> bool:
        return bool(
            self.selected_api_key
            and self.selected_secret_key
        )

    def validate_binance_activation(
        self,
    ) -> None:
        if not self.enable_binance_execution:
            return

        if not self.has_selected_credentials:
            mode = (
                "testnet"
                if self.binance_testnet
                else "live"
            )
            raise ValueError(
                "Binance execution is enabled, but "
                f"{mode} credentials are missing."
            )

        if (
            not self.binance_testnet
            and not self.enable_real_trading
        ):
            raise ValueError(
                "Binance live execution requires "
                "ENABLE_REAL_TRADING=true."
            )
