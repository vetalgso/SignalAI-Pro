from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.models.trading_signal import TradingSignal
from app.tradinggpt.data import (
    MarketDataService,
)

from .repository import (
    TradingSignalRepository,
)
from .schemas import (
    SignalStatus,
    SignalTransitionRequest,
)
from .service import (
    TERMINAL_STATUSES,
    TradingSignalService,
)


TRACKABLE_STATUSES = {
    SignalStatus.ACTIVE.value,
    SignalStatus.ENTRY_REACHED.value,
    SignalStatus.TP1_REACHED.value,
    SignalStatus.TP2_REACHED.value,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def decimal_value(
    value: object,
) -> Decimal:
    return Decimal(str(value))


def current_price_candle(
    value: object,
    *,
    observed_at: datetime,
) -> "CandleRange":
    price = decimal_value(value)

    if price <= 0:
        raise ValueError(
            "Current market price must "
            "be positive."
        )

    return CandleRange(
        opened_at=aware_datetime(
            observed_at
        ),
        high=price,
        low=price,
        close=price,
    )


@dataclass(frozen=True, slots=True)
class CandleRange:
    opened_at: datetime
    high: Decimal
    low: Decimal
    close: Decimal

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
    ) -> "CandleRange":
        raw_timestamp = payload.get(
            "open_time"
        )

        if raw_timestamp is None:
            raise ValueError(
                "Candle open_time is missing."
            )

        opened_at = datetime.fromtimestamp(
            float(raw_timestamp) / 1000,
            tz=timezone.utc,
        )

        high = decimal_value(
            payload["high"]
        )
        low = decimal_value(
            payload["low"]
        )
        close = decimal_value(
            payload["close"]
        )

        if (
            high <= 0
            or low <= 0
            or close <= 0
            or high < low
        ):
            raise ValueError(
                "Invalid candle prices."
            )

        return cls(
            opened_at=opened_at,
            high=high,
            low=low,
            close=close,
        )

    def payload(
        self,
    ) -> dict[str, str]:
        return {
            "opened_at": (
                self.opened_at.isoformat()
            ),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
        }


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    status: SignalStatus
    trigger_price: Decimal
    note: str


def level_touched(
    candle: CandleRange,
    *,
    lower: Decimal,
    upper: Decimal,
) -> bool:
    return (
        candle.high >= lower
        and candle.low <= upper
    )


def stop_touched(
    signal: TradingSignal,
    candle: CandleRange,
) -> bool:
    if signal.side == "LONG":
        return (
            candle.low
            <= signal.stop_loss
        )

    return (
        candle.high
        >= signal.stop_loss
    )


def target_touched(
    signal: TradingSignal,
    candle: CandleRange,
    target: Decimal | None,
) -> bool:
    if target is None:
        return False

    if signal.side == "LONG":
        return candle.high >= target

    return candle.low <= target


def next_transition(
    signal: TradingSignal,
    candle: CandleRange,
) -> TransitionDecision | None:
    status = signal.status

    if status == SignalStatus.ACTIVE.value:
        if level_touched(
            candle,
            lower=signal.entry_min,
            upper=signal.entry_max,
        ):
            entry_price = (
                signal.entry_min
                + signal.entry_max
            ) / Decimal("2")

            return TransitionDecision(
                status=(
                    SignalStatus
                    .ENTRY_REACHED
                ),
                trigger_price=entry_price,
                note=(
                    "Entry range reached "
                    "by market candle."
                ),
            )

        return None

    if status not in {
        SignalStatus.ENTRY_REACHED.value,
        SignalStatus.TP1_REACHED.value,
        SignalStatus.TP2_REACHED.value,
    }:
        return None

    # Conservative rule: when one candle contains
    # both a stop and a target, Stop Loss wins.
    if stop_touched(
        signal,
        candle,
    ):
        return TransitionDecision(
            status=SignalStatus.STOPPED,
            trigger_price=(
                signal.stop_loss
            ),
            note=(
                "Stop Loss reached by "
                "market candle."
            ),
        )

    if (
        status
        == SignalStatus.ENTRY_REACHED.value
        and target_touched(
            signal,
            candle,
            signal.take_profit_1,
        )
    ):
        return TransitionDecision(
            status=(
                SignalStatus.TP1_REACHED
            ),
            trigger_price=(
                signal.take_profit_1
            ),
            note=(
                "Take Profit 1 reached "
                "by market candle."
            ),
        )

    if (
        status
        == SignalStatus.TP1_REACHED.value
    ):
        if (
            signal.take_profit_2
            is not None
            and target_touched(
                signal,
                candle,
                signal.take_profit_2,
            )
        ):
            return TransitionDecision(
                status=(
                    SignalStatus
                    .TP2_REACHED
                ),
                trigger_price=(
                    signal.take_profit_2
                ),
                note=(
                    "Take Profit 2 reached "
                    "by market candle."
                ),
            )

        if (
            signal.take_profit_2 is None
            and signal.take_profit_3
            is not None
            and target_touched(
                signal,
                candle,
                signal.take_profit_3,
            )
        ):
            return TransitionDecision(
                status=(
                    SignalStatus
                    .TP3_REACHED
                ),
                trigger_price=(
                    signal.take_profit_3
                ),
                note=(
                    "Take Profit 3 reached "
                    "by market candle."
                ),
            )

    if (
        status
        == SignalStatus.TP2_REACHED.value
        and signal.take_profit_3
        is not None
        and target_touched(
            signal,
            candle,
            signal.take_profit_3,
        )
    ):
        return TransitionDecision(
            status=SignalStatus.TP3_REACHED,
            trigger_price=(
                signal.take_profit_3
            ),
            note=(
                "Take Profit 3 reached "
                "by market candle."
            ),
        )

    return None


def should_expire(
    signal: TradingSignal,
    now: datetime,
) -> bool:
    if (
        signal.status
        != SignalStatus.ACTIVE.value
    ):
        return False

    if signal.expires_at is None:
        return False

    return (
        aware_datetime(signal.expires_at)
        <= aware_datetime(now)
    )


class SignalLifecycleTracker:
    def __init__(
        self,
        repository: TradingSignalRepository,
        market_data: (
            MarketDataService | None
        ) = None,
    ) -> None:
        self.repository = repository
        self.service = TradingSignalService(
            repository
        )
        self.market_data = (
            market_data
            or MarketDataService()
        )

    async def refresh_all(
        self,
        *,
        limit: int = 500,
    ) -> dict[str, object]:
        signals = (
            self.repository
            .list_trackable(limit=limit)
        )

        groups: dict[
            str,
            list[TradingSignal],
        ] = defaultdict(list)

        for signal in signals:
            groups[signal.symbol].append(
                signal
            )

        changes: list[
            dict[str, object]
        ] = []
        errors: list[
            dict[str, str]
        ] = []

        updated_signal_ids: set[int] = (
            set()
        )
        price_updates = 0
        now = utc_now()

        for symbol, symbol_signals in (
            groups.items()
        ):
            try:
                snapshot = await (
                    self.market_data
                    .get_market_snapshot(
                        asset=symbol,
                        interval="1m",
                        candle_limit=250,
                    )
                )
            except Exception as exc:
                errors.append(
                    {
                        "symbol": symbol,
                        "error": (
                            type(exc).__name__
                        ),
                    }
                )
                continue

            candles: list[CandleRange] = []

            for raw_candle in (
                snapshot.candles
            ):
                try:
                    candles.append(
                        CandleRange
                        .from_payload(
                            raw_candle
                        )
                    )
                except Exception:
                    continue

            try:
                candles.append(
                    current_price_candle(
                        snapshot.price,
                        observed_at=now,
                    )
                )
            except (
                ArithmeticError,
                TypeError,
                ValueError,
            ):
                pass

            candles.sort(
                key=lambda item: (
                    item.opened_at
                )
            )

            for signal in symbol_signals:
                try:
                    signal_changes = (
                        self._refresh_signal(
                            signal=signal,
                            candles=candles,
                            now=now,
                        )
                    )

                    if signal_changes:
                        updated_signal_ids.add(
                            signal.id
                        )
                        changes.extend(
                            signal_changes
                        )

                    latest_price = (
                        candles[-1].close
                        if candles
                        else decimal_value(
                            snapshot.price
                        )
                    )

                    self.service.update_market_price(
                        signal_id=signal.id,
                        price=latest_price,
                        checked_at=now,
                    )
                    price_updates += 1
                except Exception as exc:
                    self.repository.db.rollback()

                    errors.append(
                        {
                            "symbol": (
                                signal.symbol
                            ),
                            "signal_id": str(
                                signal.id
                            ),
                            "error": (
                                type(exc)
                                .__name__
                            ),
                        }
                    )

        return {
            "checked_signals": len(
                signals
            ),
            "updated_signals": len(
                updated_signal_ids
            ),
            "transition_count": len(
                changes
            ),
            "price_updates": (
                price_updates
            ),
            "changes": changes,
            "errors": errors,
        }

    def _refresh_signal(
        self,
        *,
        signal: TradingSignal,
        candles: list[CandleRange],
        now: datetime,
    ) -> list[dict[str, object]]:
        changes: list[
            dict[str, object]
        ] = []

        generated_at = aware_datetime(
            signal.generated_at
        )
        updated_at = aware_datetime(
            signal.updated_at
        )

        start_at = max(
            generated_at,
            updated_at
            - timedelta(minutes=2),
        )

        expires_at = (
            aware_datetime(
                signal.expires_at
            )
            if signal.expires_at
            is not None
            else None
        )

        candidates = [
            candle
            for candle in candles
            if candle.opened_at
            >= start_at
        ]

        for candle in candidates:
            if (
                signal.status
                == SignalStatus.ACTIVE.value
                and expires_at is not None
                and candle.opened_at
                > expires_at
            ):
                break

            while (
                signal.status
                in TRACKABLE_STATUSES
            ):
                decision = next_transition(
                    signal,
                    candle,
                )

                if decision is None:
                    break

                from_status = signal.status

                self.service.transition(
                    signal_id=signal.id,
                    request=(
                        SignalTransitionRequest(
                            status=(
                                decision.status
                            ),
                            price=(
                                decision
                                .trigger_price
                            ),
                            note=decision.note,
                        )
                    ),
                    event_type=(
                        "MARKET_STATUS_CHANGED"
                    ),
                    event_payload={
                        "automatic": True,
                        "candle": (
                            candle.payload()
                        ),
                    },
                )

                changes.append(
                    {
                        "signal_id": signal.id,
                        "symbol": signal.symbol,
                        "from_status": (
                            from_status
                        ),
                        "to_status": (
                            signal.status
                        ),
                        "trigger_price": (
                            decision
                            .trigger_price
                        ),
                        "triggered_at": (
                            utc_now()
                        ),
                        "candle_opened_at": (
                            candle.opened_at
                        ),
                    }
                )

                if (
                    signal.status
                    in TERMINAL_STATUSES
                ):
                    break

            if (
                signal.status
                in TERMINAL_STATUSES
            ):
                break

        if should_expire(
            signal,
            now,
        ):
            from_status = signal.status
            price = (
                candles[-1].close
                if candles
                else signal.current_price
                or signal.entry_min
            )

            self.service.transition(
                signal_id=signal.id,
                request=(
                    SignalTransitionRequest(
                        status=(
                            SignalStatus.EXPIRED
                        ),
                        price=price,
                        note=(
                            "Signal expired before "
                            "entry was reached."
                        ),
                    )
                ),
                event_type=(
                    "MARKET_STATUS_CHANGED"
                ),
                event_payload={
                    "automatic": True,
                    "reason": (
                        "ENTRY_WINDOW_EXPIRED"
                    ),
                },
            )

            changes.append(
                {
                    "signal_id": signal.id,
                    "symbol": signal.symbol,
                    "from_status": (
                        from_status
                    ),
                    "to_status": (
                        signal.status
                    ),
                    "trigger_price": price,
                    "triggered_at": (
                        utc_now()
                    ),
                    "candle_opened_at": (
                        None
                    ),
                }
            )

        return changes
