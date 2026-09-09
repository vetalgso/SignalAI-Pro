from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.tradinggpt.orders import (
    reconciliation_service,
)
from app.tradinggpt.orders.reconciliation_service import (
    AutomaticOrderReconciliationService,
)


class FakeSession:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


class FakeRepository:
    candidates: list[object] = []
    scopes: list[tuple[int | None, int | None]] = []

    def __init__(
        self,
        session: object,
        *,
        user_id: int | None = None,
        exchange_account_id: int | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.exchange_account_id = (
            exchange_account_id
        )
        self.scopes.append(
            (
                user_id,
                exchange_account_id,
            )
        )

    def list_reconciliation_candidates(
        self,
        *,
        limit: int,
    ) -> list[object]:
        return self.candidates[:limit]


class FakeJournal:
    results: list[object | None] = []

    def __init__(
        self,
        *,
        repository: object,
    ) -> None:
        self.repository = repository

    def reconcile_remote_result(
        self,
        result: object,
    ) -> object | None:
        return self.results.pop(0)


class FakeExecution:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.calls: list[
            dict[str, str]
        ] = []

    def get_order(
        self,
        *,
        exchange: str,
        symbol: str,
        order_id: str,
    ) -> object:
        self.calls.append(
            {
                "exchange": exchange,
                "symbol": symbol,
                "order_id": order_id,
            }
        )

        if self.fail:
            raise RuntimeError(
                "Remote lookup failed."
            )

        return object()


@pytest.fixture(autouse=True)
def install_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeRepository.candidates = []
    FakeRepository.scopes = []
    FakeJournal.results = []

    monkeypatch.setattr(
        reconciliation_service,
        "TradingOrderRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        reconciliation_service,
        "JournaledOrderService",
        FakeJournal,
    )


def candidate(
    *,
    order_id: int,
    account_id: int,
) -> object:
    return SimpleNamespace(
        id=order_id,
        user_id=7,
        exchange_account_id=account_id,
        symbol="BTCUSDT",
        exchange_order_id=str(
            9000 + order_id
        ),
    )


def test_batch_is_read_only_and_scoped(
) -> None:
    session = FakeSession()
    successful = FakeExecution()
    failing = FakeExecution(fail=True)

    FakeRepository.candidates = [
        candidate(
            order_id=1,
            account_id=42,
        ),
        candidate(
            order_id=2,
            account_id=43,
        ),
    ]
    FakeJournal.results = [
        {"id": 1},
    ]

    executions = {
        42: successful,
        43: failing,
    }

    service = (
        AutomaticOrderReconciliationService(
            session=session,
            execution_service_factory=(
                lambda *,
                account_id,
                user_id: executions[
                    account_id
                ]
            ),
            batch_size=10,
        )
    )

    result = service.run_batch()

    assert result.action == "PARTIAL"
    assert result.scanned == 2
    assert result.reconciled == 1
    assert result.skipped == 0
    assert result.failed == 1
    assert session.rollback_calls == 1

    assert successful.calls == [
        {
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "order_id": "9001",
        }
    ]

    assert FakeRepository.scopes == [
        (None, None),
        (7, 42),
    ]


def test_batch_reports_no_candidates(
) -> None:
    session = FakeSession()

    service = (
        AutomaticOrderReconciliationService(
            session=session,
            execution_service_factory=(
                lambda **kwargs: (
                    pytest.fail(
                        "Execution factory "
                        "must not be called."
                    )
                )
            ),
        )
    )

    result = service.run_batch()

    assert result.action == "NO_CANDIDATES"
    assert result.scanned == 0
    assert result.failed == 0
    assert session.rollback_calls == 0


def test_batch_reports_missing_local_order(
) -> None:
    session = FakeSession()
    execution = FakeExecution()

    FakeRepository.candidates = [
        candidate(
            order_id=3,
            account_id=44,
        ),
    ]
    FakeJournal.results = [
        None,
    ]

    service = (
        AutomaticOrderReconciliationService(
            session=session,
            execution_service_factory=(
                lambda **kwargs: execution
            ),
        )
    )

    result = service.run_batch()

    assert result.action == "RECONCILED"
    assert result.reconciled == 0
    assert result.skipped == 1
    assert result.failed == 0
