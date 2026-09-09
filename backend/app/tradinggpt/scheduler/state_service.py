from __future__ import annotations

from .state_repository import (
    SchedulerStateRepository,
)


class SchedulerStateService:
    def __init__(
        self,
        repository: SchedulerStateRepository,
    ) -> None:
        self._repository = repository

    def get(self) -> dict[str, object]:
        return self.serialize(
            self._repository.get_or_create()
        )

    def update(
        self,
        *,
        enabled: bool | None,
        interval_seconds: int | None,
    ) -> dict[str, object]:
        state = self._repository.update(
            enabled=enabled,
            interval_seconds=interval_seconds,
        )

        return self.serialize(state)

    @staticmethod
    def serialize(
        state: object,
    ) -> dict[str, object]:
        return {
            "enabled": state.enabled,
            "interval_seconds": (
                state.interval_seconds
            ),
            "last_run_at": state.last_run_at,
            "next_run_at": state.next_run_at,
            "last_cycle_id": state.last_cycle_id,
            "consecutive_failures": (
                state.consecutive_failures
            ),
            "updated_at": state.updated_at,
        }
