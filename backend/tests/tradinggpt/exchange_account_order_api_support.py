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
