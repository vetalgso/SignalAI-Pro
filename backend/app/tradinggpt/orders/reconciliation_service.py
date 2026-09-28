from __future__ import annotations

from collections.abc import Callable
from dataclasses import (
    asdict,
    dataclass,
)

from sqlalchemy.orm import Session

from .execution_service import (
    OrderExecutionService,
)
from .journal_service import (
    JournaledOrderService,
)
from .repository import (
    TradingOrderRepository,
)


ExecutionServiceFactory = Callable[
    ...,
    OrderExecutionService,
]


@dataclass(frozen=True, slots=True)
class OrderReconciliationCandidate:
    order_id: int
    user_id: int
    exchange_account_id: int
    symbol: str
    exchange_order_id: str


@dataclass(frozen=True, slots=True)
class OrderReconciliationBatchResult:
    action: str
    scanned: int
    reconciled: int
    skipped: int
    failed: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AutomaticOrderReconciliationService:
    """
    Refresh existing scoped Binance orders.

    This service only reads remote order state through
    get_order(). It never submits or cancels orders.
    """

    def __init__(
        self,
        *,
        session: Session,
        execution_service_factory: (
            ExecutionServiceFactory
        ),
        batch_size: int = 50,
    ) -> None:
        if batch_size < 1:
            raise ValueError(
                "Reconciliation batch size must "
                "be greater than zero."
            )

        self._session = session
        self._execution_service_factory = (
            execution_service_factory
        )
        self._batch_size = batch_size

    def run_batch(
        self,
    ) -> OrderReconciliationBatchResult:
        rows = (
            TradingOrderRepository(
                self._session
            )
            .list_reconciliation_candidates(
                limit=self._batch_size
            )
        )

        candidates = [
            OrderReconciliationCandidate(
                order_id=row.id,
                user_id=int(row.user_id),
                exchange_account_id=int(
                    row.exchange_account_id
                ),
                symbol=row.symbol,
                exchange_order_id=str(
                    row.exchange_order_id
                ),
            )
            for row in rows
        ]

        if not candidates:
            return OrderReconciliationBatchResult(
                action="NO_CANDIDATES",
                scanned=0,
                reconciled=0,
                skipped=0,
                failed=0,
                errors=(),
            )

        reconciled = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        for candidate in candidates:
            try:
                execution = (
                    self
                    ._execution_service_factory(
                        account_id=(
                            candidate
                            .exchange_account_id
                        ),
                        user_id=candidate.user_id,
                    )
                )

                result = execution.get_order(
                    exchange="BINANCE",
                    symbol=candidate.symbol,
                    order_id=(
                        candidate
                        .exchange_order_id
                    ),
                )

                scoped_repository = (
                    TradingOrderRepository(
                        self._session,
                        user_id=(
                            candidate.user_id
                        ),
                        exchange_account_id=(
                            candidate
                            .exchange_account_id
                        ),
                    )
                )

                reconciled_order = (
                    JournaledOrderService(
                        repository=(
                            scoped_repository
                        )
                    )
                    .reconcile_remote_result(
                        result
                    )
                )
            except Exception as exc:
                self._session.rollback()
                failed += 1
                errors.append(
                    "Order "
                    f"{candidate.order_id}: "
                    f"{exc}"
                )
                continue

            if reconciled_order is None:
                skipped += 1
            else:
                reconciled += 1

        if failed and not reconciled:
            action = "FAILED"
        elif failed:
            action = "PARTIAL"
        else:
            action = "RECONCILED"

        return OrderReconciliationBatchResult(
            action=action,
            scanned=len(candidates),
            reconciled=reconciled,
            skipped=skipped,
            failed=failed,
            errors=tuple(errors),
        )
