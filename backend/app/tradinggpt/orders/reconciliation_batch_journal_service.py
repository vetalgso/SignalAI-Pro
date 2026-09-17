from __future__ import annotations

from typing import Protocol

from .reconciliation_batch_repository import (
    OrderReconciliationBatchRepository,
)
from .reconciliation_service import (
    OrderReconciliationBatchResult,
)


FAILURE_ACTIONS = frozenset({
    "FAILED",
    "PARTIAL",
})


class OrderReconciliationBatchRunner(
    Protocol
):
    def run_batch(
        self,
    ) -> OrderReconciliationBatchResult:
        ...


class JournaledOrderReconciliationBatchService:
    """
    Persist one automatic reconciliation run.

    Remote operations remain read-only. Unexpected
    failures are journaled and then re-raised so the
    background loop keeps its LOOP_ERROR behavior.
    """

    def __init__(
        self,
        *,
        runner: OrderReconciliationBatchRunner,
        repository: (
            OrderReconciliationBatchRepository
        ),
        source: str = "BINANCE_TESTNET",
        history_limit: int = 100_000,
    ) -> None:
        if history_limit < 1:
            raise ValueError(
                "Reconciliation history limit "
                "must be greater than zero."
            )

        self._runner = runner
        self._repository = repository
        self._source = source
        self._history_limit = history_limit

    def run_batch(
        self,
    ) -> dict[str, object]:
        batch = self._repository.create_started(
            source=self._source,
            read_only=True,
        )

        try:
            result = self._runner.run_batch()
        except Exception as exc:
            self._repository.rollback()

            message = (
                str(exc).strip()
                or exc.__class__.__name__
            )

            self._repository.finish(
                batch=batch,
                action="FAILED",
                scanned=0,
                reconciled=0,
                skipped=0,
                failed=1,
                errors=(message,),
                error_message=message,
            )

            raise

        action = result.action.strip().upper()
        error_message = self._error_message(
            action=action,
            errors=result.errors,
        )

        stored = self._repository.finish(
            batch=batch,
            action=action,
            scanned=result.scanned,
            reconciled=result.reconciled,
            skipped=result.skipped,
            failed=result.failed,
            errors=result.errors,
            error_message=error_message,
        )

        pruned_batches = (
            self._prune_history(
                latest_batch_id=stored.id
            )
        )

        payload = result.to_dict()
        payload.update({
            "action": stored.action,
            "batch_id": stored.id,
            "history_limit": (
                self._history_limit
            ),
            "pruned_batches": pruned_batches,
            "source": stored.source,
            "read_only": stored.read_only,
            "started_at": (
                stored.started_at.isoformat()
            ),
            "finished_at": (
                stored.finished_at.isoformat()
                if stored.finished_at
                else None
            ),
            "error_message": (
                stored.error_message
            ),
        })

        if stored.error_message:
            payload["reason"] = (
                stored.error_message
            )

        return payload

    def _prune_history(
        self,
        *,
        latest_batch_id: int,
    ) -> int:
        cutoff_id = (
            latest_batch_id
            - self._history_limit
            + 1
        )

        return (
            self._repository
            .prune_finished_before(
                batch_id=cutoff_id
            )
        )

    @staticmethod
    def _error_message(
        *,
        action: str,
        errors: tuple[str, ...],
    ) -> str | None:
        if action not in FAILURE_ACTIONS:
            return None

        messages = [
            str(error).strip()
            for error in errors
            if str(error).strip()
        ]

        if messages:
            return "; ".join(messages)

        return (
            "Reconciliation batch completed "
            f"with action {action}."
        )
