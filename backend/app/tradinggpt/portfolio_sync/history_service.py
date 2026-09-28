from __future__ import annotations

from app.models.portfolio_snapshot import (
    PortfolioSnapshotRecord,
)

from .analytics import PortfolioAnalyticsService
from .models import PortfolioSnapshot
from .repository import PortfolioSnapshotRepository


class PortfolioHistoryService:
    def __init__(
        self,
        *,
        repository: PortfolioSnapshotRepository,
    ) -> None:
        self._repository = repository
        self._analytics = PortfolioAnalyticsService()

    def save(
        self,
        snapshot: PortfolioSnapshot,
    ) -> PortfolioSnapshotRecord:
        record = self._repository.create(snapshot)
        self._repository._session.commit()
        self._repository._session.refresh(record)
        return record

    def get(
        self,
        snapshot_id: int,
    ) -> PortfolioSnapshotRecord | None:
        return self._repository.get(snapshot_id)

    def list_history(
        self,
        *,
        source: str | None,
        limit: int,
    ) -> list[PortfolioSnapshotRecord]:
        return self._repository.list_recent(
            source=source,
            limit=limit,
        )

    def analytics(
        self,
        *,
        source: str,
        limit: int,
    ) -> dict[str, object]:
        records = (
            self._repository.list_chronological(
                source=source,
                limit=limit,
            )
        )

        return self._analytics.calculate(
            source=source,
            records=records,
        ).to_dict()

    @staticmethod
    def serialize(
        record: PortfolioSnapshotRecord,
    ) -> dict[str, object]:
        return {
            "id": record.id,
            "source": record.source,
            "total_wallet_balance": (
                float(record.total_wallet_balance)
                if record.total_wallet_balance
                is not None
                else None
            ),
            "balances_count": record.balances_count,
            "open_orders_count": (
                record.open_orders_count
            ),
            "positions_count": (
                record.positions_count
            ),
            "snapshot_payload": (
                record.snapshot_payload
            ),
            "captured_at": record.captured_at,
            "created_at": record.created_at,
        }
