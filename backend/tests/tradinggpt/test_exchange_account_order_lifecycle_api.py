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
    order_router as exchange_account_router,
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


def test_history_uses_authenticated_account_scope(
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
    repository_calls: list[
        dict[str, object]
    ] = []
    list_calls: list[
        dict[str, object]
    ] = []

    class FakeHistoryRepository:
        def list_recent(
            self,
            *,
            limit: int,
            exchange: str | None,
            symbol: str | None,
            status: str | None,
        ) -> list[object]:
            list_calls.append(
                {
                    "limit": limit,
                    "exchange": exchange,
                    "symbol": symbol,
                    "status": status,
                }
            )

            return []

    def repository_factory(
        selected_db: object,
        *,
        user_id: int,
        exchange_account_id: int,
    ) -> FakeHistoryRepository:
        repository_calls.append(
            {
                "db": selected_db,
                "user_id": user_id,
                "exchange_account_id": (
                    exchange_account_id
                ),
            }
        )

        return FakeHistoryRepository()

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

    install_auth_overrides(db)

    try:
        response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/history",
            params={
                "limit": 10,
                "symbol": "btcusdt",
                "status": "OPEN",
            },
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200
    assert response.json() == []

    assert account_service.get_calls == [
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

    assert list_calls == [
        {
            "limit": 10,
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "status": "OPEN",
        }
    ]


def test_remote_lifecycle_uses_authenticated_account(
    client: TestClient,
    monkeypatch: object,
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

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "reconcile_exchange_order_result",
        lambda *args, **kwargs: None,
    )

    install_auth_overrides(db)

    try:
        opened = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/open",
            params={"symbol": "btcusdt"},
        )
        status_response = client.get(
            "/api/v3/exchange/accounts/"
            "42/orders/9001",
            params={"symbol": "btcusdt"},
        )
        canceled = client.delete(
            "/api/v3/exchange/accounts/"
            "42/orders/9001",
            params={"symbol": "btcusdt"},
        )
    finally:
        clear_auth_overrides()

    assert opened.status_code == 200
    assert status_response.status_code == 200
    assert canceled.status_code == 200

    assert (
        opened.json()[0]["status"]
        == "OPEN"
    )
    assert (
        status_response.json()["status"]
        == "OPEN"
    )
    assert (
        canceled.json()["status"]
        == "CANCELED"
    )

    assert account_service.calls == [
        {"account_id": 42, "user_id": 7},
        {"account_id": 42, "user_id": 7},
        {"account_id": 42, "user_id": 7},
    ]

    assert execution.calls == [
        {
            "operation": "open",
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
        },
        {
            "operation": "status",
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "order_id": "9001",
        },
        {
            "operation": "cancel",
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "order_id": "9001",
        },
    ]

    assert db.rollback_calls == 0
