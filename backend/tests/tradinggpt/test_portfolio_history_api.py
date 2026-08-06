from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.portfolio_sync.history_service import (
    PortfolioHistoryService,
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
        captured_at=datetime.now(timezone.utc),
    )


def test_history_service_saves_and_reads() -> None:
    with build_session() as session:
        service = PortfolioHistoryService(
            repository=(
                PortfolioSnapshotRepository(
                    session
                )
            )
        )

        saved = service.save(
            snapshot(equity=10_000.0)
        )
        stored = service.get(saved.id)

        assert stored is not None
        assert stored.id == saved.id
        assert float(
            stored.total_wallet_balance
        ) == 10_000.0


def test_history_service_lists_recent() -> None:
    with build_session() as session:
        service = PortfolioHistoryService(
            repository=(
                PortfolioSnapshotRepository(
                    session
                )
            )
        )

        service.save(
            snapshot(equity=10_000.0)
        )
        service.save(
            snapshot(equity=10_500.0)
        )

        results = service.list_history(
            source="PAPER",
            limit=10,
        )

        assert len(results) == 2
        assert float(
            results[0].total_wallet_balance
        ) == 10_500.0


def test_history_service_returns_analytics() -> None:
    with build_session() as session:
        service = PortfolioHistoryService(
            repository=(
                PortfolioSnapshotRepository(
                    session
                )
            )
        )

        service.save(
            snapshot(equity=10_000.0)
        )
        service.save(
            snapshot(equity=9_000.0)
        )

        result = service.analytics(
            source="PAPER",
            limit=100,
        )

        assert result["current_equity"] == 9_000.0
        assert result["max_drawdown"] == 1_000.0
        assert (
            result["max_drawdown_percent"]
            == 10.0
        )
