from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.order_reconciliation_batch import (
    OrderReconciliationBatch,
)


MAX_BATCH_ERRORS = 100
MAX_BATCH_ERROR_LENGTH = 1000


class OrderReconciliationBatchRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create_started(
        self,
        *,
        source: str = "BINANCE_TESTNET",
        read_only: bool = True,
    ) -> OrderReconciliationBatch:
        normalized_source = source.strip().upper()

        if not normalized_source:
            raise ValueError(
                "Reconciliation source "
                "must not be empty."
            )

        batch = OrderReconciliationBatch(
            action="STARTED",
            source=normalized_source,
            read_only=read_only,
        )

        self._session.add(batch)
        self._session.commit()
        self._session.refresh(batch)

        return batch

    def finish(
        self,
        *,
        batch: OrderReconciliationBatch,
        action: str,
        scanned: int,
        reconciled: int,
        skipped: int,
        failed: int,
        errors: Sequence[str] = (),
        error_message: str | None = None,
    ) -> OrderReconciliationBatch:
        normalized_action = action.strip().upper()

        if not normalized_action:
            raise ValueError(
                "Reconciliation action "
                "must not be empty."
            )

        counts = {
            "scanned": scanned,
            "reconciled": reconciled,
            "skipped": skipped,
            "failed": failed,
        }

        invalid = [
            name
            for name, value in counts.items()
            if value < 0
        ]

        if invalid:
            raise ValueError(
                "Reconciliation counts must "
                f"not be negative: {invalid}"
            )

        normalized_errors = [
            str(error)[:MAX_BATCH_ERROR_LENGTH]
            for error in list(errors)[
                :MAX_BATCH_ERRORS
            ]
        ]

        batch.action = normalized_action
        batch.scanned = scanned
        batch.reconciled = reconciled
        batch.skipped = skipped
        batch.failed = failed
        batch.errors = normalized_errors or None
        batch.error_message = (
            str(error_message)[
                :MAX_BATCH_ERROR_LENGTH
            ]
            if error_message
            else None
        )
        batch.finished_at = datetime.now(
            timezone.utc
        )

        self._session.add(batch)
        self._session.commit()
        self._session.refresh(batch)

        return batch

    def rollback(self) -> None:
        self._session.rollback()

    def prune_finished_before(
        self,
        *,
        batch_id: int,
    ) -> int:
        if batch_id <= 1:
            return 0

        result = self._session.execute(
            delete(
                OrderReconciliationBatch
            )
            .where(
                OrderReconciliationBatch.id
                < batch_id
            )
            .where(
                OrderReconciliationBatch
                .finished_at
                .is_not(None)
            )
        )
        self._session.commit()

        rowcount = getattr(
            result,
            "rowcount",
            0,
        )

        return max(
            0,
            int(rowcount or 0),
        )

    def get(
        self,
        batch_id: int,
    ) -> OrderReconciliationBatch | None:
        return self._session.get(
            OrderReconciliationBatch,
            batch_id,
        )

    def list_recent(
        self,
        *,
        action: str | None = None,
        limit: int = 100,
    ) -> list[OrderReconciliationBatch]:
        if limit <= 0:
            raise ValueError(
                "Reconciliation batch limit "
                "must be greater than zero."
            )

        statement = select(
            OrderReconciliationBatch
        )

        if action is not None:
            statement = statement.where(
                OrderReconciliationBatch.action
                == action.strip().upper()
            )

        statement = statement.order_by(
            OrderReconciliationBatch.id.desc()
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )

    def count_by_action(
        self,
    ) -> dict[str, int]:
        statement = (
            select(
                OrderReconciliationBatch.action,
                func.count(
                    OrderReconciliationBatch.id
                ),
            )
            .group_by(
                OrderReconciliationBatch.action
            )
            .order_by(
                OrderReconciliationBatch.action
            )
        )

        rows = self._session.execute(
            statement
        ).all()

        return {
            str(action).upper(): int(count)
            for action, count in rows
        }
