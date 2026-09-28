from __future__ import annotations

from typing import Any

from .repository import SchedulerCycleRepository
from .service import SafeSchedulerCycleService
from .state_repository import (
    SchedulerStateRepository,
)


class JournaledSchedulerCycleService:
    def __init__(
        self,
        *,
        cycle_service: SafeSchedulerCycleService,
        repository: SchedulerCycleRepository,
        state_repository: (
            SchedulerStateRepository | None
        ) = None,
    ) -> None:
        self._cycle_service = cycle_service
        self._repository = repository
        self._state_repository = state_repository

    def run(
        self,
        *,
        account: object,
        limits: object | None = None,
    ) -> dict[str, object]:
        cycle = self._repository.create_started(
            dry_run=True
        )

        try:
            result = self._cycle_service.run(
                account=account,
                limits=limits,
            )

            stored = self._repository.finish(
                cycle=cycle,
                status=str(result["status"]),
                risk_payload=self._dict_or_none(
                    result.get("risk")
                ),
                execution_payload=(
                    self._dict_or_none(
                        result.get("execution")
                    )
                ),
            )

            self._record_runtime_state(stored)

            return {
                **result,
                "cycle_id": stored.id,
                "started_at": stored.started_at,
                "finished_at": stored.finished_at,
                "error_message": None,
            }
        except Exception as exc:
            stored = self._repository.finish(
                cycle=cycle,
                status="FAILED",
                risk_payload=None,
                execution_payload=None,
                error_message=str(exc),
            )

            self._record_runtime_state(stored)

            return {
                "status": "FAILED",
                "dry_run": True,
                "risk": {},
                "execution": None,
                "reason": (
                    "Scheduler cycle failed."
                ),
                "cycle_id": stored.id,
                "started_at": stored.started_at,
                "finished_at": stored.finished_at,
                "error_message": str(exc),
            }

    def _record_runtime_state(
        self,
        cycle: object,
    ) -> None:
        if self._state_repository is None:
            return

        self._state_repository.record_cycle(
            cycle_id=cycle.id,
            cycle_status=cycle.status,
            finished_at=cycle.finished_at,
        )

    def get(
        self,
        cycle_id: int,
    ) -> dict[str, object] | None:
        cycle = self._repository.get(cycle_id)

        if cycle is None:
            return None

        return self.serialize(cycle)

    def list_recent(
        self,
        *,
        status: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        return [
            self.serialize(cycle)
            for cycle in self._repository.list_recent(
                status=status,
                limit=limit,
            )
        ]

    @staticmethod
    def serialize(
        cycle: object,
    ) -> dict[str, object]:
        return {
            "cycle_id": cycle.id,
            "status": cycle.status,
            "dry_run": cycle.dry_run,
            "risk": cycle.risk_payload or {},
            "execution": cycle.execution_payload,
            "reason": (
                "Scheduler cycle failed."
                if cycle.status == "FAILED"
                else None
            ),
            "started_at": cycle.started_at,
            "finished_at": cycle.finished_at,
            "error_message": cycle.error_message,
        }

    @staticmethod
    def _dict_or_none(
        value: object,
    ) -> dict[str, Any] | None:
        if value is None:
            return None

        if not isinstance(value, dict):
            raise TypeError(
                "Scheduler payload must be a dictionary."
            )

        return value
