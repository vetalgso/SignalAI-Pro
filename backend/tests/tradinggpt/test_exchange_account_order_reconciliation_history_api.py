from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.tradinggpt.exchange_accounts import (
    order_router as exchange_account_router,
)

from tests.tradinggpt.exchange_account_order_api_support import (
    FakeDb,
    FakeExchangeAccountService,
    FakeExecutionService,
    clear_auth_overrides,
    install_auth_overrides,
)


class FakeBatchRepository:
    def __init__(
        self,
        batches: list[object],
    ) -> None:
        self.batches = batches
        self.calls: list[
            dict[str, object]
        ] = []

    def list_recent(
        self,
        *,
        action: str | None,
        limit: int,
    ) -> list[object]:
        self.calls.append({
            "action": action,
            "limit": limit,
        })

        return self.batches


def test_reconciliation_history_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v3/exchange/accounts/"
        "42/orders/reconciliation/history"
    )

    assert response.status_code == 401


def test_reconciliation_history_uses_owned_account(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    db = FakeDb()
    account_service = (
        FakeExchangeAccountService(
            FakeExecutionService()
        )
    )
    repository = FakeBatchRepository([
        SimpleNamespace(
            id=32,
            action="PARTIAL",
            source="BINANCE_TESTNET",
            read_only=True,
            scanned=3,
            reconciled=2,
            skipped=0,
            failed=1,
            errors=[
                "Order 7: remote lookup failed."
            ],
            error_message=(
                "Order 7: remote lookup failed."
            ),
            started_at=now,
            finished_at=now,
        ),
    ])

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "OrderReconciliationBatchRepository",
        lambda _: repository,
    )

    install_auth_overrides(db)

    try:
        response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/reconciliation/history"
            "?limit=25&action=partial"
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["account_id"] == 42
    assert payload[0]["batch_id"] == 32
    assert payload[0]["action"] == "PARTIAL"
    assert payload[0]["source"] == (
        "BINANCE_TESTNET"
    )
    assert payload[0]["read_only"] is True
    assert payload[0]["scanned"] == 3
    assert payload[0]["reconciled"] == 2
    assert payload[0]["failed"] == 1
    assert payload[0]["errors"] == [
        "Order 7: remote lookup failed."
    ]

    assert repository.calls == [
        {
            "action": "PARTIAL",
            "limit": 25,
        }
    ]
    assert account_service.get_calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]
    assert account_service.calls == []
    assert db.rollback_calls == 0
