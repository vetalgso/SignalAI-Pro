from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from typing import Any

from app.models.trading_signal import (
    TradingSignal,
    TradingSignalEvent,
)

from .repository import TradingSignalRepository
from .schemas import (
    SignalCreateRequest,
    SignalSide,
    SignalStatus,
    SignalTransitionRequest,
)


TERMINAL_STATUSES = {
    SignalStatus.TP3_REACHED.value,
    SignalStatus.STOPPED.value,
    SignalStatus.EXPIRED.value,
    SignalStatus.CANCELLED.value,
}

ALLOWED_TRANSITIONS = {
    SignalStatus.ACTIVE.value: {
        SignalStatus.ENTRY_REACHED.value,
        SignalStatus.EXPIRED.value,
        SignalStatus.CANCELLED.value,
    },
    SignalStatus.ENTRY_REACHED.value: {
        SignalStatus.TP1_REACHED.value,
        SignalStatus.STOPPED.value,
        SignalStatus.CANCELLED.value,
    },
    SignalStatus.TP1_REACHED.value: {
        SignalStatus.TP2_REACHED.value,
        SignalStatus.TP3_REACHED.value,
        SignalStatus.STOPPED.value,
        SignalStatus.CANCELLED.value,
    },
    SignalStatus.TP2_REACHED.value: {
        SignalStatus.TP3_REACHED.value,
        SignalStatus.STOPPED.value,
        SignalStatus.CANCELLED.value,
    },
}


class SignalNotFoundError(Exception):
    pass


class DuplicateSignalError(Exception):
    def __init__(
        self,
        existing_signal_id: int,
    ) -> None:
        self.existing_signal_id = (
            existing_signal_id
        )

        super().__init__(
            "Duplicate trading signal. "
            f"Existing signal ID: "
            f"{existing_signal_id}."
        )


class InvalidSignalTransitionError(
    Exception
):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TradingSignalService:
    def __init__(
        self,
        repository: TradingSignalRepository,
    ) -> None:
        self.repository = repository

    @staticmethod
    def _fingerprint(
        request: SignalCreateRequest,
    ) -> str:
        generated_bucket = (
            request.generated_at
            .astimezone(timezone.utc)
            .replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            .isoformat()
        )

        payload = {
            "exchange": request.exchange,
            "market_type": (
                request.market_type.value
            ),
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "side": request.side.value,
            "strategy": request.strategy,
            "entry_min": str(
                request.entry_min
            ),
            "entry_max": str(
                request.entry_max
            ),
            "stop_loss": str(
                request.stop_loss
            ),
            "take_profit_1": str(
                request.take_profit_1
            ),
            "generated_bucket": (
                generated_bucket
            ),
        }

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha256(
            encoded
        ).hexdigest()

    @staticmethod
    def _risk_reward(
        request: SignalCreateRequest,
    ) -> Decimal:
        midpoint = (
            request.entry_min
            + request.entry_max
        ) / Decimal("2")

        if request.side == SignalSide.LONG:
            risk = (
                midpoint
                - request.stop_loss
            )
            reward = (
                request.take_profit_1
                - midpoint
            )
        else:
            risk = (
                request.stop_loss
                - midpoint
            )
            reward = (
                midpoint
                - request.take_profit_1
            )

        if risk <= 0 or reward <= 0:
            raise ValueError(
                "Signal risk and reward "
                "must be positive."
            )

        return (
            reward / risk
        ).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )

    def create(
        self,
        request: SignalCreateRequest,
    ) -> TradingSignal:
        fingerprint = self._fingerprint(
            request
        )

        existing = (
            self.repository
            .get_by_fingerprint(
                fingerprint
            )
        )

        if existing is not None:
            raise DuplicateSignalError(
                existing.id
            )

        signal = TradingSignal(
            fingerprint=fingerprint,
            exchange=request.exchange,
            market_type=(
                request.market_type.value
            ),
            symbol=request.symbol,
            timeframe=request.timeframe,
            side=request.side.value,
            strategy=request.strategy,
            status=(
                SignalStatus.ACTIVE.value
            ),
            confidence=request.confidence,
            risk_level=(
                request.risk_level.value
            ),
            risk_reward=(
                self._risk_reward(request)
            ),
            entry_min=request.entry_min,
            entry_max=request.entry_max,
            stop_loss=request.stop_loss,
            take_profit_1=(
                request.take_profit_1
            ),
            take_profit_2=(
                request.take_profit_2
            ),
            take_profit_3=(
                request.take_profit_3
            ),
            current_price=(
                request.current_price
            ),
            reasons=request.reasons,
            metadata_payload=(
                request.metadata_payload
            ),
            source=request.source,
            generated_at=(
                request.generated_at
            ),
            expires_at=request.expires_at,
            activated_at=(
                request.generated_at
            ),
        )

        self.repository.add(signal)

        self.repository.add_event(
            signal_id=signal.id,
            event_type="CREATED",
            from_status=None,
            to_status=signal.status,
            price=signal.current_price,
            note=(
                "Trading signal created."
            ),
            payload={
                "source": signal.source,
                "strategy": (
                    signal.strategy
                ),
            },
        )

        self.repository.db.commit()
        self.repository.db.refresh(signal)

        return signal

    def get(
        self,
        signal_id: int,
    ) -> TradingSignal:
        signal = self.repository.get(
            signal_id
        )

        if signal is None:
            raise SignalNotFoundError(
                f"Trading signal not found: "
                f"{signal_id}."
            )

        return signal

    def list(
        self,
        **filters: object,
    ) -> tuple[
        list[TradingSignal],
        int,
    ]:
        return self.repository.list(
            **filters
        )

    def events(
        self,
        signal_id: int,
    ) -> list[TradingSignalEvent]:
        self.get(signal_id)

        return (
            self.repository.list_events(
                signal_id
            )
        )

    def update_market_price(
        self,
        *,
        signal_id: int,
        price: Decimal,
        checked_at: datetime | None = None,
    ) -> TradingSignal:
        signal = self.get(signal_id)

        signal.current_price = price
        signal.updated_at = (
            checked_at or utc_now()
        )

        self.repository.db.commit()
        self.repository.db.refresh(signal)

        return signal

    def transition(
        self,
        *,
        signal_id: int,
        request: SignalTransitionRequest,
        event_type: str = "STATUS_CHANGED",
        event_payload: dict[str, Any]
        | None = None,
    ) -> TradingSignal:
        signal = self.get(signal_id)

        from_status = signal.status
        to_status = request.status.value

        if from_status in TERMINAL_STATUSES:
            raise InvalidSignalTransitionError(
                "Terminal signal cannot "
                "change status."
            )

        allowed = ALLOWED_TRANSITIONS.get(
            from_status,
            set(),
        )

        if to_status not in allowed:
            raise InvalidSignalTransitionError(
                "Invalid signal transition: "
                f"{from_status} -> "
                f"{to_status}."
            )

        now = utc_now()

        signal.status = to_status
        signal.updated_at = now

        if request.price is not None:
            signal.current_price = (
                request.price
            )

        if (
            to_status
            == SignalStatus.ENTRY_REACHED.value
        ):
            signal.entry_reached_at = now

        if to_status in TERMINAL_STATUSES:
            signal.closed_at = now

        self.repository.add_event(
            signal_id=signal.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            price=request.price,
            note=request.note,
            payload=event_payload,
        )

        self.repository.db.commit()
        self.repository.db.refresh(signal)

        return signal
