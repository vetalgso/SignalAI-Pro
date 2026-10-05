from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.positions.preview_monitor import (
    LivePositionPreviewService,
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


def create_long(
    repository: TradingPositionRepository,
    *,
    price_source: str = "BINANCE_PUBLIC",
    maximum: float = 25.0,
):
    return repository.create(
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        price_source=price_source,
        max_price_deviation_percent=maximum,
    )


@pytest.mark.anyio
async def test_preview_does_not_mutate_position() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        session.commit()

        service = LivePositionPreviewService(
            position_repository=repository,
            price_provider=FakePriceProvider(
                {"BTCUSDT": 110.0}
            ),
        )

        result = await service.preview(
            exchange="PAPER"
        )

        session.refresh(position)

        assert result["preview_only"] is True
        assert result["previewed_positions"] == 1
        assert position.status == "OPEN"
        assert float(
            position.remaining_quantity
        ) == 1.0
        assert position.tp1_triggered is False
        assert float(position.stop_loss) == 90.0

        preview = result["results"][0]

        assert preview["status"] == (
            "PARTIALLY_CLOSED"
        )
        assert preview[
            "remaining_quantity"
        ] == 0.5
        assert "TAKE_PROFIT_1" in preview[
            "actions"
        ]


@pytest.mark.anyio
async def test_preview_stop_loss_without_close() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        session.commit()

        service = LivePositionPreviewService(
            position_repository=repository,
            price_provider=FakePriceProvider(
                {"BTCUSDT": 90.0}
            ),
        )

        result = await service.preview(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["results"][0][
            "status"
        ] == "CLOSED"
        assert result["results"][0][
            "actions"
        ] == ["STOP_LOSS"]

        assert position.status == "OPEN"
        assert float(
            position.realized_pnl
        ) == 0.0


@pytest.mark.anyio
async def test_preview_ignores_manual() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        create_long(
            repository,
            price_source="MANUAL",
        )
        session.commit()

        provider = FakePriceProvider(
            {"BTCUSDT": 110.0}
        )
        service = LivePositionPreviewService(
            position_repository=repository,
            price_provider=provider,
        )

        result = await service.preview(
            exchange="PAPER"
        )

        assert result["checked_positions"] == 0
        assert result["results"] == []
        assert provider.calls == []


@pytest.mark.anyio
async def test_preview_rejects_anomaly() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(
            repository,
            maximum=10.0,
        )
        session.commit()

        service = LivePositionPreviewService(
            position_repository=repository,
            price_provider=FakePriceProvider(
                {"BTCUSDT": 50.0}
            ),
        )

        result = await service.preview(
            exchange="PAPER"
        )
        session.refresh(position)

        assert result["previewed_positions"] == 0
        assert len(
            result["rejected_positions"]
        ) == 1
        assert position.status == "OPEN"


@pytest.mark.anyio
async def test_preview_does_not_create_events() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        create_long(repository)
        session.commit()

        service = LivePositionPreviewService(
            position_repository=repository,
            price_provider=FakePriceProvider(
                {"BTCUSDT": 110.0}
            ),
        )

        await service.preview(
            exchange="PAPER"
        )

        event_count = session.execute(
            __import__("sqlalchemy").text(
                "SELECT COUNT(*) "
                "FROM position_events"
            )
        ).scalar_one()

        assert event_count == 0
