from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.models.order_reconciliation_batch import (
    OrderReconciliationBatch,
)
from app.tradinggpt.orders.reconciliation_batch_journal_service import (
    JournaledOrderReconciliationBatchService,
)
from app.tradinggpt.orders.reconciliation_batch_repository import (
    OrderReconciliationBatchRepository,
)
from app.tradinggpt.orders.reconciliation_service import (
    OrderReconciliationBatchResult,
)


class FakeRunner:
    def __init__(
        self,
        *,
        result: (
            OrderReconciliationBatchResult
            | None
        ) = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def run_batch(
        self,
    ) -> OrderReconciliationBatchResult:
        self.calls += 1

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise AssertionError(
                "Fake reconciliation result "
                "was not configured."
            )

        return self.result


@pytest.fixture
def session() -> Iterator[Session]:
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

    with factory() as database_session:
        yield database_session

    engine.dispose()


def test_partial_batch_is_persisted(
    session: Session,
) -> None:
    runner = FakeRunner(
        result=OrderReconciliationBatchResult(
            action="PARTIAL",
            scanned=3,
            reconciled=2,
            skipped=0,
            failed=1,
            errors=(
                "Order 7: remote lookup failed.",
            ),
        )
    )
    repository = (
        OrderReconciliationBatchRepository(
            session
        )
    )
    service = (
        JournaledOrderReconciliationBatchService(
            runner=runner,
            repository=repository,
        )
    )

    payload = service.run_batch()

    assert runner.calls == 1
    assert payload["action"] == "PARTIAL"
    assert payload["batch_id"] == 1
    assert payload["source"] == (
        "BINANCE_TESTNET"
    )
    assert payload["read_only"] is True
    assert payload["scanned"] == 3
    assert payload["reconciled"] == 2
    assert payload["failed"] == 1
    assert payload["started_at"] is not None
    assert payload["finished_at"] is not None
    assert payload["reason"] == (
        "Order 7: remote lookup failed."
    )

    stored = repository.get(
        int(payload["batch_id"])
    )

    assert stored is not None
    assert stored.action == "PARTIAL"
    assert stored.read_only is True
    assert stored.scanned == 3
    assert stored.reconciled == 2
    assert stored.failed == 1
    assert stored.errors == [
        "Order 7: remote lookup failed."
    ]
    assert stored.error_message == (
        "Order 7: remote lookup failed."
    )
    assert stored.finished_at is not None


def test_no_candidates_batch_is_persisted(
    session: Session,
) -> None:
    runner = FakeRunner(
        result=OrderReconciliationBatchResult(
            action="NO_CANDIDATES",
            scanned=0,
            reconciled=0,
            skipped=0,
            failed=0,
            errors=(),
        )
    )
    repository = (
        OrderReconciliationBatchRepository(
            session
        )
    )

    payload = (
        JournaledOrderReconciliationBatchService(
            runner=runner,
            repository=repository,
        )
        .run_batch()
    )

    assert payload["action"] == (
        "NO_CANDIDATES"
    )
    assert payload["error_message"] is None
    assert "reason" not in payload

    stored = repository.get(
        int(payload["batch_id"])
    )

    assert stored is not None
    assert stored.action == "NO_CANDIDATES"
    assert stored.scanned == 0
    assert stored.failed == 0
    assert stored.errors is None
    assert stored.error_message is None


def test_unexpected_error_is_persisted_and_reraised(
    session: Session,
) -> None:
    runner = FakeRunner(
        error=RuntimeError(
            "Synthetic batch crash."
        )
    )
    repository = (
        OrderReconciliationBatchRepository(
            session
        )
    )
    service = (
        JournaledOrderReconciliationBatchService(
            runner=runner,
            repository=repository,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic batch crash",
    ):
        service.run_batch()

    batches = repository.list_recent()

    assert len(batches) == 1

    stored = batches[0]

    assert stored.action == "FAILED"
    assert stored.read_only is True
    assert stored.scanned == 0
    assert stored.reconciled == 0
    assert stored.skipped == 0
    assert stored.failed == 1
    assert stored.errors == [
        "Synthetic batch crash."
    ]
    assert stored.error_message == (
        "Synthetic batch crash."
    )
    assert stored.finished_at is not None


def test_service_prunes_finished_history(
    session: Session,
) -> None:
    runner = FakeRunner(
        result=OrderReconciliationBatchResult(
            action="NO_CANDIDATES",
            scanned=0,
            reconciled=0,
            skipped=0,
            failed=0,
            errors=(),
        )
    )
    repository = (
        OrderReconciliationBatchRepository(
            session
        )
    )
    service = (
        JournaledOrderReconciliationBatchService(
            runner=runner,
            repository=repository,
            history_limit=2,
        )
    )

    first = service.run_batch()
    second = service.run_batch()
    third = service.run_batch()

    assert first["pruned_batches"] == 0
    assert second["pruned_batches"] == 0
    assert third["pruned_batches"] == 1
    assert third["history_limit"] == 2

    batches = repository.list_recent(
        limit=10
    )

    assert [
        batch.id
        for batch in batches
    ] == [
        int(third["batch_id"]),
        int(second["batch_id"]),
    ]

    with pytest.raises(
        ValueError,
        match="history limit",
    ):
        JournaledOrderReconciliationBatchService(
            runner=runner,
            repository=repository,
            history_limit=0,
        )
