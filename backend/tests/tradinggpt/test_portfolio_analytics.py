from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.portfolio_snapshot import (
    PortfolioSnapshotRecord,
)
from app.tradinggpt.portfolio_sync.analytics import (
    PortfolioAnalyticsService,
)
from app.tradinggpt.portfolio_sync.models import (
    AssetBalance,
    PortfolioSnapshot,
)
from app.tradinggpt.portfolio_sync.repository import (
    PortfolioSnapshotRepository,
)


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


def snapshot(
    *,
    equity: float,
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        source="PAPER",
        balances=[
            AssetBalance(
                asset="USDT",
                free=equity,
                locked=0.0,
            )
        ],
        total_wallet_balance=equity,
    )


def record(
    *,
    record_id: int,
    equity: float,
) -> PortfolioSnapshotRecord:
    return PortfolioSnapshotRecord(
        id=record_id,
        source="PAPER",
        total_wallet_balance=Decimal(
            str(equity)
        ),
        balances_count=1,
        open_orders_count=0,
        positions_count=0,
        snapshot_payload={},
        captured_at=datetime(
            2026,
            8,
            record_id,
            tzinfo=timezone.utc,
        ),
    )


def test_repository_saves_snapshot() -> None:
    with build_session() as session:
        repository = (
            PortfolioSnapshotRepository(
                session
            )
        )

        saved = repository.create(
            snapshot(equity=10_000.0)
        )
        session.commit()

        stored = repository.get(saved.id)

        assert stored is not None
        assert stored.source == "PAPER"
        assert float(
            stored.total_wallet_balance
        ) == 10_000.0
        assert stored.balances_count == 1


def test_repository_filters_by_source() -> None:
    with build_session() as session:
        repository = (
            PortfolioSnapshotRepository(
                session
            )
        )

        repository.create(
            snapshot(equity=10_000.0)
        )

        other = snapshot(
            equity=20_000.0
        ).model_copy(
            update={"source": "BINANCE"}
        )
        repository.create(other)
        session.commit()

        results = repository.list_recent(
            source="PAPER"
        )

        assert len(results) == 1
        assert results[0].source == "PAPER"


def test_analytics_calculates_equity_change() -> None:
    result = PortfolioAnalyticsService().calculate(
        source="PAPER",
        records=[
            record(
                record_id=1,
                equity=10_000.0,
            ),
            record(
                record_id=2,
                equity=10_500.0,
            ),
        ],
    )

    assert result.current_equity == 10_500.0
    assert result.equity_change == 500.0
    assert result.equity_change_percent == 5.0


def test_analytics_calculates_max_drawdown() -> None:
    result = PortfolioAnalyticsService().calculate(
        source="PAPER",
        records=[
            record(
                record_id=1,
                equity=10_000.0,
            ),
            record(
                record_id=2,
                equity=12_000.0,
            ),
            record(
                record_id=3,
                equity=9_000.0,
            ),
            record(
                record_id=4,
                equity=11_000.0,
            ),
        ],
    )

    assert result.peak_equity == 12_000.0
    assert result.max_drawdown == 3_000.0
    assert result.max_drawdown_percent == 25.0
    assert result.current_drawdown == 1_000.0


def test_analytics_handles_empty_equity() -> None:
    result = PortfolioAnalyticsService().calculate(
        source="PAPER",
        records=[],
    )

    assert result.snapshots_count == 0
    assert result.current_equity is None
    assert result.equity_curve == ()
