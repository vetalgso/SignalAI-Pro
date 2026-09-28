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


class FakeBackgroundLoop:
    def status(self) -> object:
        now = datetime.now(timezone.utc)

        return SimpleNamespace(
            running=True,
            stopping=False,
            poll_interval_seconds=15.0,
            iterations=12,
            failed_ticks=1,
            started_at=now,
            stopped_at=None,
            last_tick_started_at=now,
            last_tick_finished_at=now,
            last_action="RECONCILED",
            last_error=None,
        )


def test_reconciliation_status_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v3/exchange/accounts/"
        "42/orders/reconciliation/status"
    )

    assert response.status_code == 401


def test_reconciliation_status_uses_owned_account(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    account_service = (
        FakeExchangeAccountService(
            FakeExecutionService()
        )
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "order_reconciliation_background_loop",
        FakeBackgroundLoop(),
    )
    monkeypatch.setattr(
        exchange_account_router.settings,
        "order_reconciliation_background_enabled",
        True,
    )
    monkeypatch.setattr(
        exchange_account_router.settings,
        "order_reconciliation_batch_size",
        50,
    )

    install_auth_overrides(db)

    try:
        response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/reconciliation/status"
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    payload = response.json()

    assert payload["account_id"] == 42
    assert payload["source"] == "BINANCE_TESTNET"
    assert payload["enabled"] is True
    assert payload["read_only"] is True
    assert payload["running"] is True
    assert payload["iterations"] == 12
    assert payload["failed_ticks"] == 1
    assert payload["last_action"] == "RECONCILED"
    assert payload["last_error"] is None
    assert payload["batch_size"] == 50

    assert account_service.get_calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]
    assert account_service.calls == []
    assert db.rollback_calls == 0
