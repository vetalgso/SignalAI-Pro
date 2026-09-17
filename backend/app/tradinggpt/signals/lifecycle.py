from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from .history import MINUTE, minute_ceiling

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
            not all(value.is_finite() for value in (high, low, close))
            or high <= 0
            or low <= 0
            or close <= 0
            or high < low
            or not low <= close <= high
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


class LifecycleHistoryGap(ValueError):
    """A requested closed-candle page is missing or invalid."""


class LifecycleBoundaryAmbiguous(ValueError):
    """A candle cannot resolve an entry before a sub-minute deadline."""


def validated_history_page(raw: list[dict[str, Any]], *, start: datetime,
                           end: datetime) -> list[CandleRange]:
    """Reject latest-only, short, duplicate, unordered and incomplete pages."""
    expected = int((end - start) / MINUTE)
    if not isinstance(raw, list) or len(raw) != expected:
        raise LifecycleHistoryGap("Incomplete page")
    result = []
    for index, item in enumerate(raw):
        try:
            candle = CandleRange.from_payload(item)
            wanted = start + index * MINUTE
            close_ms = int((wanted + MINUTE).timestamp() * 1000) - 1
            if candle.opened_at != wanted or item.get("close_time") != close_ms:
                raise ValueError("Unexpected candle interval")
        except (ArithmeticError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            raise LifecycleHistoryGap("Invalid historical candle") from exc
        result.append(candle)
    return result


class SignalLifecycleTracker:
    # One bounded page per signal/cycle. Longer outages resume durably on the
    # next cycle; never jump forward to the latest snapshot to catch up.
    HISTORY_PAGE_SIZE = 1000

    def __init__(self, repository: TradingSignalRepository,
                 market_data: MarketDataService | None = None) -> None:
        self.repository = repository
        self.service = TradingSignalService(repository)
        self.market_data = market_data or MarketDataService()

    def _locked_signal(self, signal_id: int) -> TradingSignal | None:
        return self.repository.get_for_update(signal_id)

    async def refresh_all(self, *, limit: int = 500) -> dict[str, object]:
        db = self.repository.db
        signal_ids = [s.id for s in self.repository.list_trackable(limit=limit)]
        # Do not hold a row lock or a stale ORM snapshot during network IO.
        db.rollback()
        changes: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []
        updated_signal_ids: set[int] = set()
        price_updates = 0
        now = utc_now()
        cutoff = now.replace(second=0, microsecond=0)

        for signal_id in signal_ids:
            start = None
            symbol = ""
            try:
                signal = db.get(TradingSignal, signal_id)
                if signal is None or signal.status not in TRACKABLE_STATUSES:
                    db.rollback()
                    continue
                symbol, status = signal.symbol, signal.status
                history_status = signal.lifecycle_history_status
                if signal.lifecycle_next_candle_at is None or history_status == "UNVERIFIED":
                    errors.append({"symbol": symbol, "signal_id": str(signal_id),
                                   "error": "LifecycleHistoryUnverified"})
                    db.rollback()
                    continue
                if (signal.exchange, signal.market_type) != ("BINANCE", "SPOT"):
                    signal.lifecycle_history_status = "UNSUPPORTED"
                    db.commit()
                    errors.append({"symbol": symbol, "signal_id": str(signal_id),
                                   "error": "LifecycleUnsupportedMarket"})
                    continue
                start = aware_datetime(signal.lifecycle_next_candle_at)
                if start != start.replace(second=0, microsecond=0):
                    raise LifecycleHistoryGap("Cursor is not minute aligned")
                if start < minute_ceiling(signal.generated_at):
                    raise LifecycleHistoryGap("Cursor precedes signal creation")
                if (signal.expires_at is not None
                        and start == minute_ceiling(signal.generated_at)
                        and aware_datetime(signal.expires_at) < start):
                    raise LifecycleBoundaryAmbiguous("No full minute in entry window")
                if start >= cutoff:
                    # Waiting for the first/next fully closed minute is normal.
                    db.rollback()
                    continue
                end = min(cutoff, start + self.HISTORY_PAGE_SIZE * MINUTE)
                db.rollback()
                raw = await self.market_data.get_candle_history(
                    asset=symbol, start_at=start, end_at=end,
                    limit=int((end - start) / MINUTE),
                )
                candles = validated_history_page(raw, start=start, end=end)
                signal = self._locked_signal(signal_id)
                if (signal is None or signal.status != status
                        or signal.lifecycle_next_candle_at is None
                        or aware_datetime(signal.lifecycle_next_candle_at) != start
                        or signal.lifecycle_history_status != history_status):
                    # Another worker/operator advanced this signal while we fetched.
                    db.rollback()
                    continue
                page_changes = self._process_page(signal, candles, now)
                signal.lifecycle_history_status = (
                    "CURRENT" if signal.status in TERMINAL_STATUSES
                    or aware_datetime(signal.lifecycle_next_candle_at) >= cutoff
                    else "BACKFILL"
                )
                signal.updated_at = now
                pending = signal.lifecycle_history_status == "BACKFILL"
                # Transitions, outbox messages, price and cursor are atomic.
                db.commit()
                changes.extend(page_changes)
                if page_changes:
                    updated_signal_ids.add(signal_id)
                price_updates += 1
                if pending:
                    errors.append({"symbol": symbol, "signal_id": str(signal_id),
                                   "error": "LifecycleBackfillPending"})
            except Exception as exc:
                db.rollback()
                # Keep the old cursor and status transitions on every failure.
                # Mark the coverage failure only if no other worker advanced it.
                signal = self._locked_signal(signal_id)
                if (signal is not None and start is not None
                        and signal.lifecycle_next_candle_at is not None
                        and aware_datetime(signal.lifecycle_next_candle_at) == start
                        and signal.status in TRACKABLE_STATUSES):
                    signal.lifecycle_history_status = "GAP"
                    db.commit()
                else:
                    db.rollback()
                errors.append({"symbol": symbol, "signal_id": str(signal_id),
                               "error": type(exc).__name__})
        return {
            "checked_signals": len(signal_ids),
            "updated_signals": len(updated_signal_ids),
            "transition_count": len(changes), "price_updates": price_updates,
            "changes": changes, "errors": errors,
        }

    def _process_page(self, signal: TradingSignal, candles: list[CandleRange],
                      now: datetime) -> list[dict[str, object]]:
        changes = []
        expires = aware_datetime(signal.expires_at) if signal.expires_at else None
        for candle in candles:
            if signal.status == SignalStatus.ACTIVE.value and expires is not None:
                if candle.opened_at > expires:
                    # Earlier candles have been checked; no need to inspect later ones.
                    break
                if (candle.opened_at <= expires < candle.opened_at + MINUTE
                        and level_touched(candle, lower=signal.entry_min, upper=signal.entry_max)):
                    # OHLC cannot tell if entry happened before or after expiry.
                    raise LifecycleBoundaryAmbiguous("Entry crosses expiry boundary")
            while signal.status in TRACKABLE_STATUSES:
                decision = next_transition(signal, candle)
                if decision is None:
                    break
                from_status = signal.status
                self.service.transition(
                    signal_id=signal.id,
                    request=SignalTransitionRequest(
                        status=decision.status, price=decision.trigger_price, note=decision.note,
                    ),
                    event_type="MARKET_STATUS_CHANGED", commit=False,
                    event_payload={
                        "automatic": True, "candle": candle.payload(),
                        "history": {"policy": "CLOSED_1M_V1",
                                    "coverage_from": minute_ceiling(signal.generated_at).isoformat(),
                                    "covered_until": (candle.opened_at + MINUTE).isoformat()},
                    },
                )
                changes.append({
                    "signal_id": signal.id, "symbol": signal.symbol,
                    "from_status": from_status, "to_status": signal.status,
                    "trigger_price": decision.trigger_price, "triggered_at": utc_now(),
                    "candle_opened_at": candle.opened_at,
                })
            signal.lifecycle_next_candle_at = candle.opened_at + MINUTE
            signal.current_price = candle.close
            if signal.status in TERMINAL_STATUSES:
                break
        if (should_expire(signal, now) and expires is not None
                and aware_datetime(signal.lifecycle_next_candle_at) > expires):
            # The deadline is behind the verified cursor, not merely wall time.
            price = signal.current_price or signal.entry_min
            self.service.transition(
                signal_id=signal.id,
                request=SignalTransitionRequest(
                    status=SignalStatus.EXPIRED, price=price,
                    note="Signal expired after its entry window was checked.",
                ),
                event_type="MARKET_STATUS_CHANGED", commit=False,
                event_payload={"automatic": True, "reason": "ENTRY_WINDOW_EXPIRED",
                               "history": {"policy": "CLOSED_1M_V1",
                                           "covered_until": signal.lifecycle_next_candle_at.isoformat()}},
            )
            changes.append({"signal_id": signal.id, "symbol": signal.symbol,
                            "from_status": "ACTIVE", "to_status": signal.status,
                            "trigger_price": price, "triggered_at": utc_now(),
                            "candle_opened_at": None})
        return changes
