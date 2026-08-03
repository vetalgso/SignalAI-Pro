from __future__ import annotations

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.positions.event_repository import (
    PositionEventRepository,
)
from app.tradinggpt.positions.live_monitor import (
    LivePositionMonitorService,
)
from app.tradinggpt.positions.monitor import (
    PositionMonitorService,
)
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
)


class FakeLivePriceProvider:
    def __init__(
        self,
        *,
        prices: dict[str, float],
        failures: dict[str, str] | None = None,
    ) -> None:
        self.prices = prices
        self.failures = failures or {}
        self.calls: list[str] = []

    async def get_price(
        self,
        symbol: str,
    ) -> float:
        self.calls.append(symbol)

        if symbol in self.failures:
            raise RuntimeError(
                self.failures[symbol]
            )

        return self.prices[symbol]


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def build_service(
    session: Session,
    provider: FakeLivePriceProvider,
) -> tuple[
    LivePositionMonitorService,
    TradingPositionRepository,
    PositionEventRepository,
]:
    positions = TradingPositionRepository(
        session
    )
    events = PositionEventRepository(session)

    monitor = PositionMonitorService(
        position_repository=positions,
        event_repository=events,
    )

    service = LivePositionMonitorService(
        position_repository=positions,
        monitor_service=monitor,
        price_provider=provider,
    )

    return service, positions, events


def create_long(
    repository: TradingPositionRepository,
    *,
    symbol: str = "BTCUSDT",
):
    return repository.create(
        exchange="PAPER",
        market_type="SPOT",
        symbol=symbol,
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        price_source="BINANCE_PUBLIC",
        max_price_deviation_percent=1000.0,
    )


@pytest.mark.anyio
async def test_live_monitor_fetches_price_and_updates() -> None:
    with build_session() as session:
        provider = FakeLivePriceProvider(
            prices={"BTCUSDT": 105.0}
        )
        service, positions, events = (
            build_service(session, provider)
        )
        position = create_long(positions)
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )

        session.refresh(position)

        assert result["updated_positions"] == 1
        assert result["prices"] == {
            "BTCUSDT": 105.0
        }
        assert result["price_errors"] == {}
        assert float(
            position.unrealized_pnl
        ) == 5.0
        assert provider.calls == ["BTCUSDT"]
        assert (
            events.list_events()[0].event_type
            == "PRICE_UPDATED"
        )


@pytest.mark.anyio
async def test_live_monitor_fetches_each_symbol_once() -> None:
    with build_session() as session:
        provider = FakeLivePriceProvider(
            prices={
                "BTCUSDT": 105.0,
                "ETHUSDT": 205.0,
            }
        )
        service, positions, _ = (
            build_service(session, provider)
        )

        create_long(
            positions,
            symbol="BTCUSDT",
        )
        create_long(
            positions,
            symbol="BTCUSDT",
        )
        create_long(
            positions,
            symbol="ETHUSDT",
        )
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )

        assert result["checked_positions"] == 3
        assert result["updated_positions"] == 3
        assert provider.calls == [
            "BTCUSDT",
            "ETHUSDT",
        ]


@pytest.mark.anyio
async def test_live_monitor_records_price_failure() -> None:
    with build_session() as session:
        provider = FakeLivePriceProvider(
            prices={},
            failures={
                "BTCUSDT": (
                    "Temporary market-data failure."
                )
            },
        )
        service, positions, events = (
            build_service(session, provider)
        )

        create_long(positions)
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )

        assert result["updated_positions"] == 0
        assert result["missing_symbols"] == [
            "BTCUSDT"
        ]
        assert result["price_errors"] == {
            "BTCUSDT": (
                "Temporary market-data failure."
            )
        }
        assert events.list_events() == []


@pytest.mark.anyio
async def test_live_monitor_triggers_tp1() -> None:
    with build_session() as session:
        provider = FakeLivePriceProvider(
            prices={"BTCUSDT": 110.0}
        )
        service, positions, events = (
            build_service(session, provider)
        )
        position = create_long(positions)
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )

        session.refresh(position)

        assert result["updated_positions"] == 1
        assert position.status == (
            "PARTIALLY_CLOSED"
        )
        assert float(position.stop_loss) == 100.0

        event_types = {
            event.event_type
            for event in events.list_events()
        }

        assert event_types == {
            "TAKE_PROFIT_1",
            "BREAK_EVEN",
        }


@pytest.mark.anyio
async def test_live_monitor_without_positions() -> None:
    with build_session() as session:
        provider = FakeLivePriceProvider(
            prices={}
        )
        service, _, _ = build_service(
            session,
            provider,
        )

        result = await service.monitor(
            exchange="PAPER"
        )

        assert result["checked_positions"] == 0
        assert result["updated_positions"] == 0
        assert result["requested_symbols"] == []
        assert result["prices"] == {}
        assert provider.calls == []
