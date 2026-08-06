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


class ExchangeAccountDeleteResponse(
    BaseModel
):
    deleted: bool
    account_id: int
