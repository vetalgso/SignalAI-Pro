from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SignalSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SignalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ENTRY_REACHED = "ENTRY_REACHED"
    TP1_REACHED = "TP1_REACHED"
    TP2_REACHED = "TP2_REACHED"
    TP3_REACHED = "TP3_REACHED"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SignalRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SignalMarketType(str, Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class SignalCreateRequest(BaseModel):
    exchange: str = Field(
        default="BINANCE",
        min_length=2,
        max_length=24,
    )
    market_type: SignalMarketType = (
        SignalMarketType.SPOT
    )
    symbol: str = Field(
        min_length=3,
        max_length=32,
        examples=["BTCUSDT"],
    )
    timeframe: str = Field(
        min_length=2,
        max_length=16,
        examples=["1h"],
    )
    side: SignalSide
    strategy: str = Field(
        min_length=2,
        max_length=100,
        examples=["trend_momentum"],
    )

    confidence: Decimal = Field(
        ge=0,
        le=100,
    )
    risk_level: SignalRiskLevel

    entry_min: Decimal = Field(gt=0)
    entry_max: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit_1: Decimal = Field(gt=0)
    take_profit_2: Decimal | None = Field(
        default=None,
        gt=0,
    )
    take_profit_3: Decimal | None = Field(
        default=None,
        gt=0,
    )
    current_price: Decimal | None = Field(
        default=None,
        gt=0,
    )

    reasons: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    metadata_payload: dict[
        str,
        Any,
    ] = Field(default_factory=dict)

    source: str = Field(
        default="SCANNER",
        min_length=2,
        max_length=32,
    )
    generated_at: datetime = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )
    expires_at: datetime | None = None

    @field_validator(
        "market_type",
        "side",
        "risk_level",
        mode="before",
    )
    @classmethod
    def normalize_enum_value(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip().upper()

        return value

    @field_validator(
        "exchange",
        "symbol",
        "timeframe",
        "strategy",
        "source",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Value must not be empty."
            )

        return normalized.upper()

    @field_validator("reasons")
    @classmethod
    def normalize_reasons(
        cls,
        reasons: list[str],
    ) -> list[str]:
        normalized = []

        for reason in reasons:
            value = reason.strip()

            if value:
                normalized.append(value)

        return normalized

    @model_validator(mode="after")
    def validate_levels(
        self,
    ) -> "SignalCreateRequest":
        if self.entry_min > self.entry_max:
            raise ValueError(
                "entry_min must be less than "
                "or equal to entry_max."
            )

        if self.side == SignalSide.LONG:
            if self.stop_loss >= self.entry_min:
                raise ValueError(
                    "LONG requires stop_loss "
                    "below entry_min."
                )

            if (
                self.take_profit_1
                <= self.entry_max
            ):
                raise ValueError(
                    "LONG requires take_profit_1 "
                    "above entry_max."
                )

            if (
                self.take_profit_2 is not None
                and self.take_profit_2
                <= self.take_profit_1
            ):
                raise ValueError(
                    "LONG take_profit_2 must be "
                    "above take_profit_1."
                )

            previous = (
                self.take_profit_2
                or self.take_profit_1
            )

            if (
                self.take_profit_3 is not None
                and self.take_profit_3
                <= previous
            ):
                raise ValueError(
                    "LONG take_profit_3 must be "
                    "above previous target."
                )

        if self.side == SignalSide.SHORT:
            if self.stop_loss <= self.entry_max:
                raise ValueError(
                    "SHORT requires stop_loss "
                    "above entry_max."
                )

            if (
                self.take_profit_1
                >= self.entry_min
            ):
                raise ValueError(
                    "SHORT requires take_profit_1 "
                    "below entry_min."
                )

            if (
                self.take_profit_2 is not None
                and self.take_profit_2
                >= self.take_profit_1
            ):
                raise ValueError(
                    "SHORT take_profit_2 must be "
                    "below take_profit_1."
                )

            previous = (
                self.take_profit_2
                or self.take_profit_1
            )

            if (
                self.take_profit_3 is not None
                and self.take_profit_3
                >= previous
            ):
                raise ValueError(
                    "SHORT take_profit_3 must be "
                    "below previous target."
                )

        if (
            self.expires_at is not None
            and self.expires_at
            <= self.generated_at
        ):
            raise ValueError(
                "expires_at must be later than "
                "generated_at."
            )

        return self


class SignalTransitionRequest(BaseModel):
    status: SignalStatus
    price: Decimal | None = Field(
        default=None,
        gt=0,
    )
    note: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "status",
        mode="before",
    )
    @classmethod
    def normalize_status(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip().upper()

        return value


class SignalResponse(BaseModel):
    id: int
    fingerprint: str

    exchange: str
    market_type: str
    symbol: str
    timeframe: str
    side: str
    strategy: str
    status: str

    confidence: Decimal
    risk_level: str
    risk_reward: Decimal

    entry_min: Decimal
    entry_max: Decimal
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal | None
    take_profit_3: Decimal | None
    current_price: Decimal | None

    reasons: list[str]
    metadata_payload: dict[str, Any]
    source: str

    generated_at: datetime
    expires_at: datetime | None
    activated_at: datetime | None
    entry_reached_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class SignalEventResponse(BaseModel):
    id: int
    signal_id: int
    event_type: str
    from_status: str | None
    to_status: str
    price: Decimal | None
    note: str | None
    payload: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class SignalPageResponse(BaseModel):
    items: list[SignalResponse]
    total: int
    limit: int
    offset: int

class SignalScanRequest(BaseModel):
    assets: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    risk_level: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    min_confidence: Decimal = Field(
        default=Decimal("60"),
        ge=0,
        le=100,
    )

    @field_validator(
        "risk_level",
        mode="before",
    )
    @classmethod
    def normalize_scan_risk(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip().lower()

        return value


class SignalScanDuplicate(BaseModel):
    symbol: str
    existing_signal_id: int


class SignalScanSkipped(BaseModel):
    symbol: str
    reason: str


class SignalScanResponse(BaseModel):
    universe_source: str = "UNKNOWN"
    universe_assets: list[str] = Field(
        default_factory=list,
    )
    scanned_assets: int
    successful_assets: int
    failed_assets: int
    opportunities_found: int
    evaluated_candidates: int = 0

    created_count: int
    duplicate_count: int
    skipped_count: int

    created: list[SignalResponse]
    duplicates: list[SignalScanDuplicate]
    skipped: list[SignalScanSkipped]
    scanner_errors: list[dict[str, str]]
    rejection_reasons: dict[str, int] = Field(
        default_factory=dict,
    )


class SignalLifecycleChange(BaseModel):
    signal_id: int
    symbol: str
    from_status: str
    to_status: str
    trigger_price: Decimal
    triggered_at: datetime
    candle_opened_at: datetime | None


class SignalRefreshResponse(BaseModel):
    checked_signals: int
    updated_signals: int
    transition_count: int
    price_updates: int
    changes: list[
        SignalLifecycleChange
    ] = Field(default_factory=list)
    errors: list[
        dict[str, str]
    ] = Field(default_factory=list)
