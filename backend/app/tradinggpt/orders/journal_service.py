from __future__ import annotations

from uuid import uuid4

from app.models.trading_order import TradingOrder
from app.tradinggpt.portfolio_sync.service import (
    PortfolioSyncService,
)
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
)

from .execution_models import OrderExecutionResult
from .execution_service import (
    OrderExecutionService,
    UnsupportedOrderOperationError,
)
from .models import OrderIntent
from .repository import TradingOrderRepository
from .schemas import JournalOrderExecuteRequest
from .validation_models import OrderPreviewResult


class JournaledOrderService:
    def __init__(
        self,
        *,
        repository: TradingOrderRepository,
        execution_service: OrderExecutionService,
        portfolio_sync_service: (
            PortfolioSyncService | None
        ) = None,
        position_repository: (
            TradingPositionRepository | None
        ) = None,
    ) -> None:
        self._repository = repository
        self._execution_service = execution_service
        self._portfolio_sync_service = (
            portfolio_sync_service
        )
        self._position_repository = (
            position_repository
        )

    def execute(
        self,
        request: JournalOrderExecuteRequest,
    ) -> dict[str, object]:
        idempotency_key = (
            request.idempotency_key
            or f"auto-{uuid4().hex}"
        )

        existing = (
            self._repository.get_by_idempotency_key(
                idempotency_key
            )
        )

        if existing is not None:
            return self.serialize(
                existing,
                replayed=True,
            )

        intent = self._build_intent(request)

        order = self._repository.create(
            idempotency_key=idempotency_key,
            exchange=request.exchange,
            market_type=request.market_type,
            symbol=request.symbol.upper(),
            side=request.side,
            order_type=request.order_type,
            requested_quantity=request.quantity,
            requested_price=request.reference_price,
            dry_run=request.dry_run,
            request_payload=request.model_dump(
                mode="json"
            ),
        )

        preview = self._preview(intent)

        preview_payload = preview.to_dict()
        preview_error = (
            "; ".join(preview.errors)
            if preview.errors
            else None
        )

        self._repository.apply_preview(
            order,
            valid=preview.valid,
            normalized_quantity=(
                preview.normalized_quantity
            ),
            normalized_price=preview.normalized_price,
            preview_payload=preview_payload,
            error_message=preview_error,
        )

        if not preview.valid:
            self._repository._session.commit()
            self._repository._session.refresh(order)

            return self.serialize(order)

        if request.dry_run:
            self._repository.apply_execution(
                order,
                status="DRY_RUN",
                client_order_id=None,
                exchange_order_id=None,
                filled_quantity=0.0,
                average_price=None,
                simulated=True,
                execution_payload={
                    "dry_run": True,
                    "preview": preview_payload,
                },
            )

            self._repository._session.commit()
            self._repository._session.refresh(order)

            return self.serialize(order)

        normalized_intent = OrderIntent(
            exchange=intent.exchange,
            market_type=intent.market_type,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=preview.normalized_quantity,
            reference_price=preview.normalized_price,
            stop_loss=intent.stop_loss,
            take_profit_1=intent.take_profit_1,
            take_profit_2=intent.take_profit_2,
            leverage=intent.leverage,
            reduce_only=intent.reduce_only,
        )

        result = self._execution_service.execute(
            normalized_intent
        )

        execution_payload = result.to_dict()

        self._attach_portfolio_snapshot(
            execution_payload=execution_payload,
            source=intent.exchange,
            execution_status=result.status,
        )

        self._attach_managed_position(
            execution_payload=execution_payload,
            order=order,
            intent=normalized_intent,
            result=result,
        )

        self._repository.apply_execution(
            order,
            status=result.status,
            client_order_id=result.client_order_id,
            exchange_order_id=(
                result.exchange_order_id
            ),
            filled_quantity=result.filled_quantity,
            average_price=result.average_price,
            simulated=result.simulated,
            execution_payload=execution_payload,
            error_message=(
                result.message
                if result.status in {
                    "FAILED",
                    "REJECTED",
                }
                else None
            ),
        )

        self._repository._session.commit()
        self._repository._session.refresh(order)

        return self.serialize(order)

    def _attach_managed_position(
        self,
        *,
        execution_payload: dict[str, object],
        order: TradingOrder,
        intent: OrderIntent,
        result: OrderExecutionResult,
    ) -> None:
        if result.status != "FILLED":
            execution_payload["managed_position"] = {
                "status": "SKIPPED",
                "reason": (
                    "Position is created only for "
                    "fully filled orders."
                ),
            }
            return

        if intent.reduce_only:
            execution_payload["managed_position"] = {
                "status": "SKIPPED",
                "reason": (
                    "Reduce-only execution does not "
                    "open a new position."
                ),
            }
            return

        if result.filled_quantity <= 0:
            execution_payload["managed_position"] = {
                "status": "SKIPPED",
                "reason": "Filled quantity is zero.",
            }
            return

        entry_price = (
            result.average_price
            if result.average_price is not None
            else intent.reference_price
        )

        if entry_price is None or entry_price <= 0:
            execution_payload["managed_position"] = {
                "status": "SKIPPED",
                "reason": (
                    "A valid execution price is "
                    "required to create a position."
                ),
            }
            return

        if self._position_repository is None:
            execution_payload["managed_position"] = {
                "status": "NOT_CONFIGURED",
            }
            return

        existing = (
            self._position_repository
            .get_by_journal_order_id(order.id)
        )

        if existing is not None:
            execution_payload["managed_position"] = {
                "status": "EXISTS",
                "position_id": existing.id,
                "journal_order_id": order.id,
            }
            return

        position = self._position_repository.create(
            journal_order_id=order.id,
            exchange=intent.exchange,
            market_type=intent.market_type,
            symbol=intent.symbol,
            side=(
                "LONG"
                if intent.side == "BUY"
                else "SHORT"
            ),
            quantity=result.filled_quantity,
            entry_price=entry_price,
            stop_loss=intent.stop_loss,
            take_profit_1=intent.take_profit_1,
            take_profit_2=intent.take_profit_2,
            metadata_payload={
                "created_from": (
                    "journaled_order_execution"
                ),
                "client_order_id": (
                    result.client_order_id
                ),
                "exchange_order_id": (
                    result.exchange_order_id
                ),
                "simulated": result.simulated,
            },
        )

        execution_payload["managed_position"] = {
            "status": "CREATED",
            "position_id": position.id,
            "journal_order_id": order.id,
            "side": position.side,
            "quantity": float(
                position.initial_quantity
            ),
            "entry_price": float(
                position.entry_price
            ),
            "stop_loss": (
                float(position.stop_loss)
                if position.stop_loss is not None
                else None
            ),
            "take_profit_1": (
                float(position.take_profit_1)
                if position.take_profit_1
                is not None
                else None
            ),
            "take_profit_2": (
                float(position.take_profit_2)
                if position.take_profit_2
                is not None
                else None
            ),
        }

    def _attach_portfolio_snapshot(
        self,
        *,
        execution_payload: dict[str, object],
        source: str,
        execution_status: str,
    ) -> None:
        if execution_status not in {
            "FILLED",
            "OPEN",
            "PARTIALLY_FILLED",
        }:
            return

        if self._portfolio_sync_service is None:
            execution_payload["portfolio_sync"] = {
                "status": "NOT_CONFIGURED",
                "source": source,
            }
            return

        try:
            snapshot = (
                self._portfolio_sync_service
                .get_snapshot(source=source)
            )
        except Exception as exc:
            execution_payload["portfolio_sync"] = {
                "status": "FAILED",
                "source": source,
                "error": str(exc),
            }
            return

        execution_payload["portfolio_sync"] = {
            "status": "SYNCED",
            "source": source,
            "snapshot": snapshot.model_dump(
                mode="json"
            ),
        }

    def list_history(
        self,
        *,
        limit: int,
        exchange: str | None,
        symbol: str | None,
        status: str | None,
    ) -> list[dict[str, object]]:
        orders = self._repository.list_recent(
            limit=limit,
            exchange=exchange,
            symbol=(
                symbol.upper()
                if symbol is not None
                else None
            ),
            status=status,
        )

        return [
            self.serialize(order)
            for order in orders
        ]

    def get_history(
        self,
        journal_id: int,
    ) -> dict[str, object] | None:
        order = self._repository.get_by_id(
            journal_id
        )

        if order is None:
            return None

        return self.serialize(order)

    def _preview(
        self,
        intent: OrderIntent,
    ) -> OrderPreviewResult:
        try:
            return self._execution_service.preview(
                intent
            )
        except UnsupportedOrderOperationError:
            valid = (
                intent.quantity > 0
                and intent.reference_price is not None
            )

            errors: list[str] = []

            if intent.quantity <= 0:
                errors.append(
                    "Order quantity must be greater "
                    "than zero."
                )

            if intent.reference_price is None:
                errors.append(
                    "Reference price is required."
                )

            notional = (
                intent.quantity
                * intent.reference_price
                if intent.reference_price is not None
                else None
            )

            return OrderPreviewResult(
                exchange=intent.exchange,
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                valid=valid,
                requested_quantity=intent.quantity,
                normalized_quantity=intent.quantity,
                requested_price=(
                    intent.reference_price
                ),
                normalized_price=(
                    intent.reference_price
                ),
                estimated_notional=notional,
                available_balance=None,
                balance_asset=None,
                errors=errors,
                warnings=[
                    "Exchange-specific preview "
                    "is unavailable."
                ],
            )

    @staticmethod
    def _build_intent(
        request: JournalOrderExecuteRequest,
    ) -> OrderIntent:
        payload = request.model_dump(
            exclude={
                "idempotency_key",
                "dry_run",
            }
        )

        payload["symbol"] = request.symbol.upper()

        return OrderIntent(**payload)

    @staticmethod
    def serialize(
        order: TradingOrder,
        *,
        replayed: bool = False,
    ) -> dict[str, object]:
        return {
            "journal_id": order.id,
            "idempotency_key": (
                order.idempotency_key
            ),
            "replayed": replayed,
            "dry_run": order.dry_run,
            "exchange": order.exchange,
            "market_type": order.market_type,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "status": order.status,
            "requested_quantity": float(
                order.requested_quantity
            ),
            "normalized_quantity": (
                float(order.normalized_quantity)
                if order.normalized_quantity
                is not None
                else None
            ),
            "requested_price": (
                float(order.requested_price)
                if order.requested_price
                is not None
                else None
            ),
            "normalized_price": (
                float(order.normalized_price)
                if order.normalized_price
                is not None
                else None
            ),
            "filled_quantity": float(
                order.filled_quantity
            ),
            "average_price": (
                float(order.average_price)
                if order.average_price
                is not None
                else None
            ),
            "client_order_id": (
                order.client_order_id
            ),
            "exchange_order_id": (
                order.exchange_order_id
            ),
            "simulated": order.simulated,
            "request_payload": (
                order.request_payload
            ),
            "preview_payload": (
                order.preview_payload
            ),
            "execution_payload": (
                order.execution_payload
            ),
            "error_message": (
                order.error_message
            ),
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }
