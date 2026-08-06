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
        self.get_calls: list[
            dict[str, int]
        ] = []

    def get(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> object:
        self.get_calls.append(
            {
                "account_id": account_id,
                "user_id": user_id,
            }
        )

        return object()

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

class FakeJournalService:
    def __init__(self) -> None:
        self.request: object | None = None

    def execute(
        self,
        request: object,
    ) -> dict[str, object]:
        self.request = request

        model_dump = getattr(
            request,
            "model_dump",
        )

        request_payload = model_dump(
            mode="json"
        )

        return {
            "journal_id": 101,
            "idempotency_key": (
                request_payload[
                    "idempotency_key"
                ]
            ),
            "replayed": False,
            "dry_run": request_payload[
                "dry_run"
            ],
            "exchange": "BINANCE",
            "market_type": "SPOT",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "status": "DRY_RUN",
            "requested_quantity": 0.001,
            "normalized_quantity": 0.001,
            "requested_price": 60_000.0,
            "normalized_price": 60_000.0,
            "filled_quantity": 0.0,
            "average_price": None,
            "client_order_id": None,
            "exchange_order_id": None,
            "simulated": True,
            "request_payload": (
                request_payload
            ),
            "preview_payload": {
                "valid": True,
            },
            "execution_payload": {
                "dry_run": True,
            },
            "error_message": None,
            "created_at": (
                "2026-08-06T00:00:00Z"
            ),
            "updated_at": (
                "2026-08-06T00:00:00Z"
            ),
        }

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
    ) -> FakeJournalService:
        assert repository is not None
        assert (
            execution_service
            is execution
        )

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

class FakeLifecycleResult:
    def __init__(
        self,
        status: str,
    ) -> None:
        self.status = status

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "status": self.status,
            "client_order_id": (
                "client-9001"
            ),
            "exchange_order_id": "9001",
            "requested_quantity": 0.001,
            "filled_quantity": 0.0,
            "average_price": None,
            "simulated": True,
            "message": (
                f"Testnet order: "
                f"{self.status}."
            ),
        }


class FakeLifecycleExecutionService:
    def __init__(self) -> None:
        self.calls: list[
            dict[str, object]
        ] = []

    def list_open_orders(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[FakeLifecycleResult]:
        self.calls.append(
            {
                "operation": "open",
                "exchange": exchange,
                "symbol": symbol,
            }
        )

        return [
            FakeLifecycleResult("OPEN")
        ]

    def get_order(
        self,
        *,
        exchange: str,
        symbol: str,
        order_id: str,
    ) -> FakeLifecycleResult:
        self.calls.append(
            {
                "operation": "status",
                "exchange": exchange,
                "symbol": symbol,
                "order_id": order_id,
            }
        )

        return FakeLifecycleResult("OPEN")

    def cancel_order(
        self,
        *,
        exchange: str,
        symbol: str,
        order_id: str,
    ) -> FakeLifecycleResult:
        self.calls.append(
            {
                "operation": "cancel",
                "exchange": exchange,
                "symbol": symbol,
                "order_id": order_id,
            }
        )

        return FakeLifecycleResult(
            "CANCELED"
        )

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
