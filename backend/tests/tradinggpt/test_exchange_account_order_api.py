from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
)
from app.database.session import get_db
from app.main import app
from app.models.user import User
from app.tradinggpt.exchange_accounts import (
    router as exchange_account_router,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)


class FakeDb:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


class FakeExecutionService:
    def __init__(self) -> None:
        self.intent: object | None = None

    def preview(
        self,
        intent: object,
    ) -> OrderPreviewResult:
        self.intent = intent

        return OrderPreviewResult(
            exchange="BINANCE",
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            valid=True,
            requested_quantity=0.001,
            normalized_quantity=0.001,
            requested_price=60_000.0,
            normalized_price=60_000.0,
            estimated_notional=60.0,
            available_balance=1000.0,
            balance_asset="USDT",
            errors=[],
            warnings=[],
        )


class FakeExchangeAccountService:
    def __init__(
        self,
        execution: FakeExecutionService,
    ) -> None:
        self.execution = execution
        self.calls: list[
            dict[str, int]
        ] = []

    def order_execution_service(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> FakeExecutionService:
        self.calls.append(
            {
                "account_id": account_id,
                "user_id": user_id,
            }
        )

        return self.execution


def build_payload(
    *,
    exchange: str = "BINANCE",
) -> dict[str, Any]:
    return {
        "exchange": exchange,
        "market_type": "SPOT",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 0.001,
        "reference_price": 60_000.0,
        "stop_loss": 59_000.0,
        "take_profit_1": 61_000.0,
        "take_profit_2": 62_000.0,
        "leverage": 1,
        "reduce_only": False,
    }


def install_auth_overrides(
    db: FakeDb,
) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: User(
        id=7,
        username="preview-user",
        password_hash="not-used",
        is_active=True,
    )

    app.dependency_overrides[
        get_db
    ] = lambda: db


def clear_auth_overrides() -> None:
    app.dependency_overrides.pop(
        get_current_user,
        None,
    )
    app.dependency_overrides.pop(
        get_db,
        None,
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
