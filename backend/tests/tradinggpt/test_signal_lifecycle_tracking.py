from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from decimal import Decimal
from types import SimpleNamespace

from app.tradinggpt.signals.lifecycle import (
    CandleRange,
    current_price_candle,
    next_transition,
    should_expire,
)
from app.tradinggpt.signals.schemas import (
    SignalStatus,
)


def signal(
    *,
    side: str = "LONG",
    status: str = "ACTIVE",
) -> SimpleNamespace:
    return SimpleNamespace(
        side=side,
        status=status,
        entry_min=Decimal("99"),
        entry_max=Decimal("101"),
        stop_loss=(
            Decimal("95")
            if side == "LONG"
            else Decimal("105")
        ),
        take_profit_1=(
            Decimal("105")
            if side == "LONG"
            else Decimal("95")
        ),
        take_profit_2=(
            Decimal("110")
            if side == "LONG"
            else Decimal("90")
        ),
        take_profit_3=(
            Decimal("115")
            if side == "LONG"
            else Decimal("85")
        ),
        expires_at=(
            datetime.now(UTC)
            + timedelta(hours=1)
        ),
    )


def candle(
    *,
    high: str,
    low: str,
    close: str = "100",
) -> CandleRange:
    return CandleRange(
        opened_at=datetime.now(UTC),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def test_long_entry_range_is_detected(
) -> None:
    decision = next_transition(
        signal(),
        candle(
            high="102",
            low="100",
        ),
    )

    assert decision is not None
    assert (
        decision.status
        == SignalStatus.ENTRY_REACHED
    )
    assert (
        decision.trigger_price
        == Decimal("100")
    )


def test_short_entry_range_is_detected(
) -> None:
    decision = next_transition(
        signal(side="SHORT"),
        candle(
            high="100",
            low="98",
        ),
    )

    assert decision is not None
    assert (
        decision.status
        == SignalStatus.ENTRY_REACHED
    )


def test_long_stop_loss_is_detected(
) -> None:
    decision = next_transition(
        signal(
            status="ENTRY_REACHED"
        ),
        candle(
            high="102",
            low="94",
        ),
    )

    assert decision is not None
    assert (
        decision.status
        == SignalStatus.STOPPED
    )
    assert (
        decision.trigger_price
        == Decimal("95")
    )


def test_long_targets_are_detected(
) -> None:
    first = next_transition(
        signal(
            status="ENTRY_REACHED"
        ),
        candle(
            high="106",
            low="99",
        ),
    )

    second = next_transition(
        signal(
            status="TP1_REACHED"
        ),
        candle(
            high="111",
            low="100",
        ),
    )

    third = next_transition(
        signal(
            status="TP2_REACHED"
        ),
        candle(
            high="116",
            low="109",
        ),
    )

    assert first is not None
    assert second is not None
    assert third is not None

    assert (
        first.status
        == SignalStatus.TP1_REACHED
    )
    assert (
        second.status
        == SignalStatus.TP2_REACHED
    )
    assert (
        third.status
        == SignalStatus.TP3_REACHED
    )


def test_short_targets_are_detected(
) -> None:
    first = next_transition(
        signal(
            side="SHORT",
            status="ENTRY_REACHED",
        ),
        candle(
            high="101",
            low="94",
        ),
    )

    second = next_transition(
        signal(
            side="SHORT",
            status="TP1_REACHED",
        ),
        candle(
            high="96",
            low="89",
        ),
    )

    assert first is not None
    assert second is not None

    assert (
        first.status
        == SignalStatus.TP1_REACHED
    )
    assert (
        second.status
        == SignalStatus.TP2_REACHED
    )


def test_stop_wins_when_same_candle_hits_target(
) -> None:
    decision = next_transition(
        signal(
            status="ENTRY_REACHED"
        ),
        candle(
            high="106",
            low="94",
        ),
    )

    assert decision is not None
    assert (
        decision.status
        == SignalStatus.STOPPED
    )


def test_active_signal_expires(
) -> None:
    item = signal()

    item.expires_at = (
        datetime.now(UTC)
        - timedelta(seconds=1)
    )

    assert should_expire(
        item,
        datetime.now(UTC),
    )

    item.status = "ENTRY_REACHED"

    assert not should_expire(
        item,
        datetime.now(UTC),
    )


def test_current_market_price_detects_entry(
) -> None:
    observed_at = datetime.now(UTC)

    current_tick = current_price_candle(
        "100",
        observed_at=observed_at,
    )

    assert (
        current_tick.opened_at
        == observed_at
    )
    assert current_tick.high == Decimal(
        "100"
    )
    assert current_tick.low == Decimal(
        "100"
    )

    decision = next_transition(
        signal(),
        current_tick,
    )

    assert decision is not None
    assert (
        decision.status
        == SignalStatus.ENTRY_REACHED
    )
