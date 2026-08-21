from __future__ import annotations
from typing import Any

import pytest
from fastapi.testclient import TestClient
from app.api.dependencies import (
    get_current_user,
)
from app.database.session import get_db
from app.main import app
from app.models.user import User
from app.tradinggpt.exchange_accounts import (
    order_router as exchange_account_router,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
    OrderRiskUsage,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)

from tests.tradinggpt.exchange_account_order_api_support import (
    FakeDb,
    FakeExchangeAccountService,
    FakeExecutionService,
    FakeJournalService,
    FakeLifecycleExecutionService,
    FakeLifecycleResult,
    build_payload,
    clear_auth_overrides,
    install_auth_overrides,
)


@pytest.fixture(autouse=True)
def install_empty_order_risk_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        lambda *args, **kwargs: (
            OrderRiskUsage()
        ),
    )


def test_preview_requires_authentication(
    client: TestClient,
) -> None:
    clear_auth_overrides()

    response = client.post(
        "/api/v3/exchange/accounts/"
        "1/orders/preview",
        json=build_payload(),
    )

    assert response.status_code == 401


def test_preview_uses_authenticated_account(
    client: TestClient,
    monkeypatch: object,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    service = FakeExchangeAccountService(
        execution
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: service,
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            "/api/v3/exchange/accounts/"
            "42/orders/preview",
            json=build_payload(),
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200
    assert service.calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]

    assert getattr(
        execution.intent,
        "exchange",
    ) == "BINANCE"

    payload = response.json()

    assert payload["valid"] is True
    assert payload["symbol"] == "BTCUSDT"
    assert payload["balance_asset"] == "USDT"
    assert db.rollback_calls == 0


def test_preview_rejects_non_binance_exchange(
    client: TestClient,
    monkeypatch: object,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    service = FakeExchangeAccountService(
        execution
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: service,
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            "/api/v3/exchange/accounts/"
            "42/orders/preview",
            json=build_payload(
                exchange="PAPER"
            ),
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 422
    assert service.calls == []


def test_execute_requires_authentication(
    client: TestClient,
) -> None:
    clear_auth_overrides()

    payload = build_payload()
    payload["idempotency_key"] = (
        "unauthorized-execute"
    )

    response = client.post(
        "/api/v3/exchange/accounts/"
        "42/orders/execute",
        json=payload,
    )

    assert response.status_code == 401


def test_execute_defaults_to_scoped_dry_run(
    client: TestClient,
    monkeypatch: object,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    account_service = (
        FakeExchangeAccountService(
            execution
        )
    )
    journal = FakeJournalService()
    repository_calls: list[
        dict[str, object]
    ] = []

    def repository_factory(
        selected_db: object,
        *,
        user_id: int,
        exchange_account_id: int,
    ) -> object:
        repository_calls.append(
            {
                "db": selected_db,
                "user_id": user_id,
                "exchange_account_id": (
                    exchange_account_id
                ),
            }
        )

        return object()

    def journal_factory(
        *,
        repository: object,
        execution_service: object,
        risk_policy: object,
    ) -> FakeJournalService:
        assert repository is not None
        assert (
            execution_service
            is execution
        )
        assert risk_policy is not None

        return journal

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "TradingOrderRepository",
        repository_factory,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "JournaledOrderService",
        journal_factory,
    )

    install_auth_overrides(db)

    payload = build_payload()
    payload["idempotency_key"] = (
        "account-42-dry-run"
    )

    try:
        response = client.post(
            "/api/v3/exchange/accounts/"
            "42/orders/execute",
            json=payload,
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    assert account_service.calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]

    assert repository_calls == [
        {
            "db": db,
            "user_id": 7,
            "exchange_account_id": 42,
        }
    ]

    assert getattr(
        journal.request,
        "exchange",
    ) == "BINANCE"

    assert getattr(
        journal.request,
        "dry_run",
    ) is True

    result = response.json()

    assert result["journal_id"] == 101
    assert result["dry_run"] is True
    assert result["status"] == "DRY_RUN"
    assert (
        result["idempotency_key"]
        == "account-42-dry-run"
    )
    assert db.rollback_calls == 0

def test_preview_applies_testnet_risk_policy(
    client: TestClient,
    monkeypatch: object,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    service = FakeExchangeAccountService(
        execution
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_policy",
        lambda: OrderRiskPolicy.configured(
            execution_enabled=True,
            max_order_notional=50.0,
            allowed_symbols="BTCUSDT",
        ),
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            "/api/v3/exchange/accounts/"
            "42/orders/preview",
            json=build_payload(),
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    payload = response.json()

    assert payload["valid"] is False
    assert payload["estimated_notional"] == 60.0
    assert len(payload["errors"]) == 1
    assert "exceeds" in payload["errors"][0]
    assert db.rollback_calls == 0



def test_preview_applies_account_risk_usage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    service = FakeExchangeAccountService(
        execution
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_policy",
        lambda: OrderRiskPolicy.configured(
            execution_enabled=True,
            max_order_notional=100.0,
            max_daily_notional=100.0,
            max_open_orders=5,
            allowed_symbols="BTCUSDT",
        ),
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        lambda *args, **kwargs: (
            OrderRiskUsage(
                daily_notional=50.0,
                open_orders=1,
            )
        ),
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            "/api/v3/exchange/accounts/"
            "42/orders/preview",
            json=build_payload(),
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    payload = response.json()

    assert payload["valid"] is False
    assert payload["estimated_notional"] == 60.0
    assert "Projected daily notional" in (
        payload["errors"][0]
    )
    assert "110.00000000" in (
        payload["errors"][0]
    )



def test_risk_status_requires_authentication(
    client: TestClient,
) -> None:
    clear_auth_overrides()

    response = client.get(
        "/api/v3/exchange/accounts/"
        "42/orders/risk"
    )

    assert response.status_code == 401


def test_risk_status_uses_authenticated_account(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    execution = FakeExecutionService()
    service = FakeExchangeAccountService(
        execution
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_policy",
        lambda: OrderRiskPolicy.configured(
            execution_enabled=True,
            max_order_notional=100.0,
            max_daily_notional=500.0,
            max_open_orders=5,
            allowed_symbols=(
                "BTCUSDT,ETHUSDT"
            ),
        ),
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        lambda *args, **kwargs: (
            OrderRiskUsage(
                daily_notional=125.0,
                open_orders=2,
            )
        ),
    )

    install_auth_overrides(db)

    try:
        response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/risk"
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    payload = response.json()

    assert payload["source"] == (
        "BINANCE_TESTNET"
    )
    assert payload["execution_enabled"] is True
    assert payload["max_order_notional"] == 100.0
    assert payload["daily_notional"] == 125.0
    assert payload["max_daily_notional"] == 500.0
    assert (
        payload["remaining_daily_notional"]
        == 375.0
    )
    assert payload["open_orders"] == 2
    assert payload["max_open_orders"] == 5
    assert (
        payload["remaining_open_order_slots"]
        == 3
    )
    assert payload["allowed_symbols"] == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    assert (
        payload["order_submission_available"]
        is True
    )
    assert payload["period_started_at"]
    assert payload["resets_at"]

    assert service.calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]
    assert db.rollback_calls == 0
