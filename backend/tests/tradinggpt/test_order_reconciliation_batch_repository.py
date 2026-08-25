from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.order_reconciliation_batch import (
    OrderReconciliationBatch,
)
from app.tradinggpt.orders.reconciliation_batch_repository import (
    MAX_BATCH_ERROR_LENGTH,
    MAX_BATCH_ERRORS,
    OrderReconciliationBatchRepository,
)


@contextmanager
def build_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )
    OrderReconciliationBatch.__table__.create(
        engine
    )
    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    try:
        with factory() as session:
            yield session
    finally:
        engine.dispose()


def test_repository_persists_finished_batch(
) -> None:
    with build_session() as session:
        repository = (
            OrderReconciliationBatchRepository(
                session
            )
        )

        batch = repository.create_started()

        assert batch.id is not None
        assert batch.action == "STARTED"
        assert batch.source == "BINANCE_TESTNET"
        assert batch.read_only is True
        assert batch.finished_at is None

        stored = repository.finish(
            batch=batch,
            action="partial",
            scanned=3,
            reconciled=1,
            skipped=1,
            failed=1,
            errors=[
                "Order 3 lookup failed.",
            ],
            error_message=(
                "One reconciliation item failed."
            ),
        )

        assert stored.action == "PARTIAL"
        assert stored.scanned == 3
        assert stored.reconciled == 1
        assert stored.skipped == 1
        assert stored.failed == 1
        assert stored.errors == [
            "Order 3 lookup failed.",
        ]
        assert stored.finished_at is not None

        loaded = repository.get(stored.id)

        assert loaded is not None
        assert loaded.action == "PARTIAL"


def test_repository_bounds_error_payload(
) -> None:
    with build_session() as session:
        repository = (
            OrderReconciliationBatchRepository(
                session
            )
        )
        batch = repository.create_started()

        stored = repository.finish(
            batch=batch,
            action="FAILED",
            scanned=105,
            reconciled=0,
            skipped=0,
            failed=105,
            errors=[
                f"error-{index}-" + ("x" * 1200)
                for index in range(105)
            ],
            error_message="y" * 1200,
        )

        assert stored.errors is not None
        assert len(stored.errors) == MAX_BATCH_ERRORS
        assert all(
            len(error)
            <= MAX_BATCH_ERROR_LENGTH
            for error in stored.errors
        )
        assert stored.error_message is not None
        assert (
            len(stored.error_message)
            == MAX_BATCH_ERROR_LENGTH
        )


def test_repository_lists_and_counts_actions(
) -> None:
    with build_session() as session:
        repository = (
            OrderReconciliationBatchRepository(
                session
            )
        )

        for action in (
            "NO_CANDIDATES",
            "RECONCILED",
            "RECONCILED",
        ):
            batch = repository.create_started()
            repository.finish(
                batch=batch,
                action=action,
                scanned=0,
                reconciled=0,
                skipped=0,
                failed=0,
            )

        recent = repository.list_recent(
            action="reconciled",
            limit=10,
        )

        assert len(recent) == 2
        assert recent[0].id > recent[1].id
        assert repository.count_by_action() == {
            "NO_CANDIDATES": 1,
            "RECONCILED": 2,
        }


def test_repository_validates_inputs(
) -> None:
    with build_session() as session:
        repository = (
            OrderReconciliationBatchRepository(
                session
            )
        )

        with pytest.raises(
            ValueError,
            match="source",
        ):
            repository.create_started(
                source=" "
            )

        batch = repository.create_started()

        with pytest.raises(
            ValueError,
            match="negative",
        ):
            repository.finish(
                batch=batch,
                action="FAILED",
                scanned=-1,
                reconciled=0,
                skipped=0,
                failed=1,
            )

        with pytest.raises(
            ValueError,
            match="limit",
        ):
            repository.list_recent(limit=0)
