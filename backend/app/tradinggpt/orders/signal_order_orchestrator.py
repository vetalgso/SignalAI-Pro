from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.models.trading_signal import (
    TradingSignal,
)

from .models import OrderIntent
from .risk import (
    OrderRiskPolicy,
    OrderRiskUsage,
)
from .validation_models import (
    OrderPreviewResult,
)


ELIGIBLE_SIGNAL_STATUSES = frozenset(
    {
        "ACTIVE",
        "ENTRY_REACHED",
    }
)


class SignalOrderNotFoundError(
    LookupError
):
    pass


class SignalOrderIneligibleError(
    ValueError
):
    pass


class TradingSignalLookup(
    Protocol
):
    def get(
        self,
        signal_id: int,
    ) -> TradingSignal | None:
        ...


class OrderPreviewExecutor(
    Protocol
):
    def preview(
        self,
        intent: OrderIntent,
    ) -> OrderPreviewResult:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class SignalOrderPreviewPlan:
    signal_id: int
    signal_status: str
    strategy: str
    confidence: float
    risk_level: str
    timeframe: str
    intent: OrderIntent
    preview: OrderPreviewResult

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "signal_id": self.signal_id,
            "signal_status": (
                self.signal_status
            ),
            "strategy": self.strategy,
            "confidence": (
                self.confidence
            ),
            "risk_level": self.risk_level,
            "timeframe": self.timeframe,
            "intent": self.intent.to_dict(),
            "preview": (
                self.preview.to_dict()
            ),
        }


class SignalToOrderOrchestrator:
    """
    Builds a risk-checked order preview
    from a persisted TradingGPT signal.

    This service never submits or cancels
    an exchange order.
    """

    def __init__(
        self,
        *,
        signals: TradingSignalLookup,
        execution_service: (
            OrderPreviewExecutor
        ),
        risk_policy: OrderRiskPolicy,
        clock: (
            Callable[[], datetime]
            | None
        ) = None,
    ) -> None:
        self._signals = signals
        self._execution_service = (
            execution_service
        )
        self._risk_policy = risk_policy
        self._clock = (
            clock
            or (
                lambda: datetime.now(
                    timezone.utc
                )
            )
        )

    def preview(
        self,
        *,
        signal_id: int,
        quantity: float,
        usage: (
            OrderRiskUsage | None
        ) = None,
    ) -> SignalOrderPreviewPlan:
        if (
            not math.isfinite(quantity)
            or quantity <= 0
        ):
            raise SignalOrderIneligibleError(
                "Signal order quantity must "
                "be a finite positive number."
            )

        signal = self._signals.get(
            signal_id
        )

        if signal is None:
            raise SignalOrderNotFoundError(
                "Trading signal was not found: "
                f"{signal_id}."
            )

        self._validate_signal(signal)

        intent = self._build_intent(
            signal=signal,
            quantity=quantity,
        )

        preview = (
            self._execution_service
            .preview(intent)
        )

        checked_preview = (
            self._risk_policy.apply(
                preview,
                usage=usage,
                increases_exposure=True,
            )
        )

        return SignalOrderPreviewPlan(
            signal_id=signal.id,
            signal_status=signal.status,
            strategy=signal.strategy,
            confidence=float(
                signal.confidence
            ),
            risk_level=signal.risk_level,
            timeframe=signal.timeframe,
            intent=intent,
            preview=checked_preview,
        )

    def _validate_signal(
        self,
        signal: TradingSignal,
    ) -> None:
        if signal.exchange.upper() != "BINANCE":
            raise SignalOrderIneligibleError(
                "Only BINANCE signals are "
                "eligible for order preview."
            )

        if signal.market_type.upper() != "SPOT":
            raise SignalOrderIneligibleError(
                "Only SPOT signals are "
                "eligible for order preview."
            )

        if signal.side.upper() != "LONG":
            raise SignalOrderIneligibleError(
                "SPOT SHORT signals cannot "
                "increase exposure safely."
            )

        if (
            signal.status.upper()
            not in ELIGIBLE_SIGNAL_STATUSES
        ):
            raise SignalOrderIneligibleError(
                "Signal status is not eligible "
                "for order preview: "
                f"{signal.status}."
            )

        if self._is_expired(signal):
            raise SignalOrderIneligibleError(
                "Trading signal has expired."
            )

        if float(signal.entry_max) <= 0:
            raise SignalOrderIneligibleError(
                "Signal entry price must be "
                "greater than zero."
            )

    def _is_expired(
        self,
        signal: TradingSignal,
    ) -> bool:
        if signal.expires_at is None:
            return False

        expires_at = signal.expires_at
        now = self._clock()

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )

        return expires_at <= now

    @staticmethod
    def _build_intent(
        *,
        signal: TradingSignal,
        quantity: float,
    ) -> OrderIntent:
        return OrderIntent(
            exchange="BINANCE",
            market_type="SPOT",
            symbol=signal.symbol.upper(),
            side="BUY",
            order_type="LIMIT",
            quantity=quantity,
            reference_price=float(
                signal.entry_max
            ),
            stop_loss=float(
                signal.stop_loss
            ),
            take_profit_1=float(
                signal.take_profit_1
            ),
            take_profit_2=(
                float(signal.take_profit_2)
                if signal.take_profit_2
                is not None
                else None
            ),
            leverage=1,
            reduce_only=False,
        )
