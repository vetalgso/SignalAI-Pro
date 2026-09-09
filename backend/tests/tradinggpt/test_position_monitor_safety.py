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


class FakePriceProvider:
    def __init__(
        self,
        prices: dict[str, float],
    ) -> None:
        self.prices = prices
        self.calls: list[str] = []

    async def get_price(
        self,
        symbol: str,
    ) -> float:
        self.calls.append(symbol)
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
    provider: FakePriceProvider,
) -> tuple[
    LivePositionMonitorService,
    TradingPositionRepository,
]:
    positions = TradingPositionRepository(
        session
    )
    monitor = PositionMonitorService(
        position_repository=positions,
        event_repository=(
            PositionEventRepository(session)
        ),
    )

    return (
        LivePositionMonitorService(
            position_repository=positions,
            monitor_service=monitor,
            price_provider=provider,
        ),
        positions,
    )


def create_position(
    repository: TradingPositionRepository,
    *,
    price_source: str,
    entry_price: float = 100.0,
    maximum: float = 25.0,
):
    return repository.create(
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=entry_price,
        stop_loss=90.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        price_source=price_source,
        max_price_deviation_percent=maximum,
    )


def test_manual_is_default_price_source() -> None:
    with build_session() as session:
        repository = (
            TradingPositionRepository(session)
        )

        position = repository.create(
            exchange="PAPER",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="LONG",
            quantity=1.0,
            entry_price=100.0,
            stop_loss=90.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
        )

        assert position.price_source == "MANUAL"
        assert float(
            position.max_price_deviation_percent
        ) == 25.0


@pytest.mark.anyio
async def test_live_monitor_ignores_manual() -> None:
    with build_session() as session:
        provider = FakePriceProvider(
            {"BTCUSDT": 50.0}
        )
        service, repository = build_service(
            session,
            provider,
        )
        position = create_position(
            repository,
            price_source="MANUAL",
        )
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["checked_positions"] == 0
        assert provider.calls == []
        assert position.status == "OPEN"


@pytest.mark.anyio
async def test_live_monitor_accepts_binance_public() -> None:
    with build_session() as session:
        provider = FakePriceProvider(
            {"BTCUSDT": 105.0}
        )
        service, repository = build_service(
            session,
            provider,
        )
        position = create_position(
            repository,
            price_source="BINANCE_PUBLIC",
        )
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["updated_positions"] == 1
        assert float(
            position.current_price
        ) == 105.0
        assert result["rejected_positions"] == []


@pytest.mark.anyio
async def test_anomalous_price_is_rejected() -> None:
    with build_session() as session:
        provider = FakePriceProvider(
            {"BTCUSDT": 50.0}
        )
        service, repository = build_service(
            session,
            provider,
        )
        position = create_position(
            repository,
            price_source="BINANCE_PUBLIC",
            maximum=25.0,
        )
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["updated_positions"] == 0
        assert result["prices"] == {}
        assert "BTCUSDT" in result["price_errors"]
        assert len(
            result["rejected_positions"]
        ) == 1
        assert position.status == "OPEN"
        assert float(
            position.current_price
        ) == 100.0


@pytest.mark.anyio
async def test_price_inside_limit_is_applied() -> None:
    with build_session() as session:
        provider = FakePriceProvider(
            {"BTCUSDT": 80.0}
        )
        service, repository = build_service(
            session,
            provider,
        )
        position = create_position(
            repository,
            price_source="BINANCE_PUBLIC",
            maximum=25.0,
        )
        session.commit()

        result = await service.monitor(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["updated_positions"] == 1
        assert position.status == "CLOSED"
        assert result["rejected_positions"] == []


def test_repository_filters_price_source() -> None:
    with build_session() as session:
        repository = (
            TradingPositionRepository(session)
        )

        create_position(
            repository,
            price_source="MANUAL",
        )
        live = create_position(
            repository,
            price_source="BINANCE_PUBLIC",
        )
        session.commit()

        positions = repository.list_active(
            price_source="BINANCE_PUBLIC"
        )

        assert [item.id for item in positions] == [
            live.id
        ]


def test_custom_deviation_is_stored() -> None:
    with build_session() as session:
        repository = (
            TradingPositionRepository(session)
        )

        position = create_position(
            repository,
            price_source="BINANCE_PUBLIC",
            maximum=5.5,
        )

        assert float(
            position.max_price_deviation_percent
        ) == 5.5
