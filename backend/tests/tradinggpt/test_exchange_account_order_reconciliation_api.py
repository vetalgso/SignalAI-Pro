from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.tradinggpt.exchange_accounts import (
    order_router as exchange_account_router,
)
from app.tradinggpt.orders.journal_service import (
    OrderReconciliationUnavailableError,
)

from tests.tradinggpt.exchange_account_order_api_support import (
    FakeDb,
    FakeExchangeAccountService,
    FakeLifecycleExecutionService,
    clear_auth_overrides,
    install_auth_overrides,
)


class FakeReconciliationJournal:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.results: list[object] = []

    def reconcile_remote_result(
        self,
        result: object,
    ) -> None:
        if self.fail:
            raise (
                OrderReconciliationUnavailableError(
                    "Remote order state could "
                    "not be reconciled."
                )
            )

        self.results.append(result)


def test_status_and_cancel_reconcile_local_journal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    execution = (
        FakeLifecycleExecutionService()
    )
    account_service = (
        FakeExchangeAccountService(
            execution
        )
    )
    journal = FakeReconciliationJournal()
    constructor_calls: list[
        dict[str, object]
    ] = []

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )

    def journal_factory(
        **kwargs: object,
    ) -> FakeReconciliationJournal:
        constructor_calls.append(kwargs)
        return journal

    monkeypatch.setattr(
        exchange_account_router,
        "JournaledOrderService",
        journal_factory,
    )

    install_auth_overrides(db)

    try:
        status_response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/9001",
            params={
                "symbol": "btcusdt",
            },
        )

        cancel_response = client.delete(
            "/api/v3/exchange/accounts/"
            "42/orders/9001",
            params={
                "symbol": "btcusdt",
            },
        )
    finally:
        clear_auth_overrides()

    assert status_response.status_code == 200
    assert cancel_response.status_code == 200

    assert [
        getattr(result, "status")
        for result in journal.results
    ] == [
        "OPEN",
        "CANCELED",
    ]

    assert len(constructor_calls) == 2

    for call in constructor_calls:
        repository = call["repository"]

        assert getattr(
            repository,
            "_user_id",
        ) == 7
        assert getattr(
            repository,
            "_exchange_account_id",
        ) == 42
        assert (
            call["execution_service"]
            is execution
        )

    assert db.rollback_calls == 0


def test_status_returns_502_when_reconciliation_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    execution = (
        FakeLifecycleExecutionService()
    )
    account_service = (
        FakeExchangeAccountService(
            execution
        )
    )
    journal = FakeReconciliationJournal(
        fail=True
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "JournaledOrderService",
        lambda **kwargs: journal,
    )

    install_auth_overrides(db)

    try:
        response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/9001",
            params={
                "symbol": "BTCUSDT",
            },
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 502
    assert "could not be reconciled" in (
        response.json()["detail"]
    )
    assert db.rollback_calls == 1
