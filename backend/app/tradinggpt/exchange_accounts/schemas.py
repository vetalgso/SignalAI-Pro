from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)

from app.tradinggpt.orders.schemas import (
    JournalOrderExecuteRequest,
    OrderExecuteRequest,
)


class ExchangeEnvironment(
    str,
    Enum,
):
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class ExchangeAccountStatus(
    str,
    Enum,
):
    UNVERIFIED = "UNVERIFIED"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"
    UNSAFE = "UNSAFE"


class ExchangeAccountCreateRequest(
    BaseModel
):
    label: str = Field(
        default="Binance",
        min_length=1,
        max_length=80,
    )

    environment: ExchangeEnvironment = (
        ExchangeEnvironment.TESTNET
    )

    api_key: SecretStr
    secret_key: SecretStr

    @field_validator(
        "api_key",
        "secret_key",
    )
    @classmethod
    def validate_secret(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        normalized = (
            value.get_secret_value().strip()
        )

        if len(normalized) < 8:
            raise ValueError(
                "Exchange credential must "
                "contain at least 8 characters."
            )

        if len(normalized) > 512:
            raise ValueError(
                "Exchange credential is too long."
            )

        return SecretStr(normalized)

    @field_validator("label")
    @classmethod
    def normalize_label(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Account label is required."
            )

        return normalized


class ExchangeAccountResponse(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    exchange: str
    environment: ExchangeEnvironment
    label: str
    api_key_hint: str
    status: ExchangeAccountStatus

    can_trade: bool | None
    can_deposit: bool | None
    can_withdraw: bool | None

    last_checked_at: datetime | None
    last_error: str | None

    created_at: datetime
    updated_at: datetime


class ExchangeAccountOrderRequest(
    OrderExecuteRequest
):
    exchange: Literal["BINANCE"] = (
        "BINANCE"
    )


class ExchangeAccountOrderExecuteRequest(
    JournalOrderExecuteRequest
):
    exchange: Literal["BINANCE"] = (
        "BINANCE"
    )
    dry_run: bool = True


class ExchangeAccountOrderRiskResponse(
    BaseModel
):
    source: Literal["BINANCE_TESTNET"]
    execution_enabled: bool

    max_order_notional: float | None

    daily_notional: float
    max_daily_notional: float | None
    remaining_daily_notional: (
        float | None
    )

    open_orders: int
    max_open_orders: int | None
    remaining_open_order_slots: (
        int | None
    )

    allowed_symbols: list[str]
    order_submission_available: bool

    period_started_at: datetime
    resets_at: datetime


class ExchangeAccountOrderReconciliationStatusResponse(
    BaseModel
):
    account_id: int
    source: Literal["BINANCE_TESTNET"]
    enabled: bool
    read_only: Literal[True]

    poll_interval_seconds: float
    batch_size: int

    running: bool
    stopping: bool
    iterations: int
    failed_ticks: int

    started_at: datetime | None
    stopped_at: datetime | None
    last_tick_started_at: datetime | None
    last_tick_finished_at: datetime | None

    last_action: str | None
    last_error: str | None


class ExchangeAccountDeleteResponse(
    BaseModel
):
    deleted: bool
    account_id: int
