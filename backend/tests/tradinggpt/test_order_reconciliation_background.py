from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.tradinggpt.orders import (
    reconciliation_background,
)


class FakeLock:
    def __init__(
        self,
        *,
        acquired: bool,
    ) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    def try_acquire(self) -> bool:
        self.acquire_calls += 1
        return self.acquired

    def release(self) -> None:
        self.release_calls += 1


class FakeSessionContext:
    def __init__(self) -> None:
        self.session = object()
        self.enter_calls = 0
        self.exit_calls = 0

    def __enter__(self) -> object:
        self.enter_calls += 1
        return self.session

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.exit_calls += 1


class FakeAccountService:
    def __init__(self) -> None:
        self.calls: list[
            dict[str, int]
        ] = []
        self.execution = object()

    def order_execution_service(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> object:
        self.calls.append(
            {
                "account_id": account_id,
                "user_id": user_id,
            }
        )
        return self.execution


class FakeBatchResult:
    def __init__(
        self,
        payload: dict[str, object],
    ) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


class FakeBatchService:
    instances: list["FakeBatchService"] = []
    payload: dict[str, object] = {}

    def __init__(
        self,
        *,
        session: object,
        execution_service_factory: object,
        batch_size: int,
    ) -> None:
        self.session = session
        self.execution_service_factory = (
            execution_service_factory
        )
        self.batch_size = batch_size
        self.instances.append(self)

    def run_batch(self) -> FakeBatchResult:
        return FakeBatchResult(
            self.payload
        )


class FakeBatchRepository:
    instances: list[
        "FakeBatchRepository"
    ] = []

    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session
        self.instances.append(self)


class FakeJournalService:
    instances: list[
        "FakeJournalService"
    ] = []

    def __init__(
        self,
        *,
        runner: FakeBatchService,
        repository: FakeBatchRepository,
        history_limit: int,
    ) -> None:
        self.runner = runner
        self.repository = repository
        self.history_limit = history_limit
        self.instances.append(self)

    def run_batch(
        self,
    ) -> dict[str, object]:
        payload = (
            self.runner.run_batch().to_dict()
        )

        payload["history_limit"] = (
            self.history_limit
        )
        payload["pruned_batches"] = 0

        if payload.get("action") in {
            "FAILED",
            "PARTIAL",
        }:
            errors = payload.get("errors")

            if isinstance(
                errors,
                (list, tuple),
            ):
                payload["reason"] = (
                    "; ".join(
                        str(error)
                        for error in errors
                    )
                    or (
                        "Automatic reconciliation "
                        "batch failed."
                    )
                )

        return payload


@pytest.fixture(autouse=True)
def reset_batch_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeBatchService.instances = []
    FakeBatchRepository.instances = []
    FakeJournalService.instances = []

    FakeBatchService.payload = {
        "action": "NO_CANDIDATES",
        "scanned": 0,
        "reconciled": 0,
        "skipped": 0,
        "failed": 0,
        "errors": (),
    }

    monkeypatch.setattr(
        reconciliation_background,
        "OrderReconciliationBatchRepository",
        FakeBatchRepository,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "JournaledOrderReconciliationBatchService",
        FakeJournalService,
    )


def test_tick_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_background_enabled",
        False,
    )

    result = (
        reconciliation_background
        .run_order_reconciliation_background_tick()
    )

    assert (
        result["action"]
        == "SKIPPED_DISABLED"
    )


def test_tick_skips_when_lock_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = FakeLock(acquired=False)

    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_background_enabled",
        True,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "PostgresAdvisorySchedulerLock",
        lambda **kwargs: lock,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "SessionLocal",
        lambda: pytest.fail(
            "Session must not open without lock."
        ),
    )

    result = (
        reconciliation_background
        .run_order_reconciliation_background_tick()
    )

    assert result["action"] == "SKIPPED_LOCKED"
    assert lock.acquire_calls == 1
    assert lock.release_calls == 0


def test_tick_runs_batch_and_releases_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = FakeLock(acquired=True)
    session_context = FakeSessionContext()
    account_service = FakeAccountService()

    FakeBatchService.payload = {
        "action": "RECONCILED",
        "scanned": 1,
        "reconciled": 1,
        "skipped": 0,
        "failed": 0,
        "errors": (),
    }

    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_background_enabled",
        True,
    )
    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_batch_size",
        25,
    )
    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_history_limit",
        250,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "PostgresAdvisorySchedulerLock",
        lambda **kwargs: lock,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "SessionLocal",
        lambda: session_context,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "build_exchange_account_service",
        lambda session: account_service,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "AutomaticOrderReconciliationService",
        FakeBatchService,
    )

    result = (
        reconciliation_background
        .run_order_reconciliation_background_tick()
    )

    assert result["action"] == "RECONCILED"
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1
    assert session_context.enter_calls == 1
    assert session_context.exit_calls == 1

    batch = FakeBatchService.instances[0]

    assert batch.batch_size == 25
    assert batch.session is (
        session_context.session
    )

    assert len(
        FakeBatchRepository.instances
    ) == 1
    assert (
        FakeBatchRepository
        .instances[0]
        .session
        is session_context.session
    )

    assert len(
        FakeJournalService.instances
    ) == 1

    journal = FakeJournalService.instances[0]

    assert journal.runner is batch
    assert (
        journal.repository
        is FakeBatchRepository.instances[0]
    )
    assert journal.history_limit == 250

    execution = (
        batch.execution_service_factory(
            account_id=42,
            user_id=7,
        )
    )

    assert execution is account_service.execution
    assert account_service.calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]


@pytest.mark.parametrize(
    "action",
    [
        "FAILED",
        "PARTIAL",
    ],
)
def test_failed_tick_exposes_reason(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    lock = FakeLock(acquired=True)
    session_context = FakeSessionContext()

    FakeBatchService.payload = {
        "action": action,
        "scanned": 1,
        "reconciled": 0,
        "skipped": 0,
        "failed": 1,
        "errors": (
            "Order 1: remote lookup failed.",
        ),
    }

    monkeypatch.setattr(
        reconciliation_background.settings,
        "order_reconciliation_background_enabled",
        True,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "PostgresAdvisorySchedulerLock",
        lambda **kwargs: lock,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "SessionLocal",
        lambda: session_context,
    )
    monkeypatch.setattr(
        reconciliation_background,
        "build_exchange_account_service",
        lambda session: SimpleNamespace(),
    )
    monkeypatch.setattr(
        reconciliation_background,
        "AutomaticOrderReconciliationService",
        FakeBatchService,
    )

    result = (
        reconciliation_background
        .run_order_reconciliation_background_tick()
    )

    assert result["action"] == action
    assert (
        result["reason"]
        == "Order 1: remote lookup failed."
    )
    assert lock.release_calls == 1
