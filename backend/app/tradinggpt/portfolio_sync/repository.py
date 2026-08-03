from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_snapshot import (
    PortfolioSnapshotRecord,
)

from .models import PortfolioSnapshot


class PortfolioSnapshotRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        snapshot: PortfolioSnapshot,
    ) -> PortfolioSnapshotRecord:
        record = PortfolioSnapshotRecord(
            source=snapshot.source,
            total_wallet_balance=(
                Decimal(
                    str(snapshot.total_wallet_balance)
                )
                if snapshot.total_wallet_balance
                is not None
                else None
            ),
            balances_count=len(snapshot.balances),
            open_orders_count=len(
                snapshot.open_orders
            ),
            positions_count=len(
                snapshot.positions
            ),
            snapshot_payload=snapshot.model_dump(
                mode="json"
            ),
            captured_at=snapshot.captured_at,
        )

        self._session.add(record)
        self._session.flush()

        return record

    def get(
        self,
        snapshot_id: int,
    ) -> PortfolioSnapshotRecord | None:
        return self._session.get(
            PortfolioSnapshotRecord,
            snapshot_id,
        )

    def list_recent(
        self,
        *,
        source: str | None = None,
        limit: int = 100,
    ) -> list[PortfolioSnapshotRecord]:
        statement = select(
            PortfolioSnapshotRecord
        )

        if source is not None:
            statement = statement.where(
                PortfolioSnapshotRecord.source
                == source.upper()
            )

        statement = statement.order_by(
            PortfolioSnapshotRecord.captured_at
            .desc(),
            PortfolioSnapshotRecord.id.desc(),
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )

    def list_chronological(
        self,
        *,
        source: str,
        limit: int = 1000,
    ) -> list[PortfolioSnapshotRecord]:
        statement = (
            select(PortfolioSnapshotRecord)
            .where(
                PortfolioSnapshotRecord.source
                == source.upper()
            )
            .order_by(
                PortfolioSnapshotRecord.captured_at
                .asc(),
                PortfolioSnapshotRecord.id.asc(),
            )
            .limit(limit)
        )

        return list(
            self._session.scalars(statement)
        )
