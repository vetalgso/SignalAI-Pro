from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy.orm import Session

from app.models.scheduler_state import SchedulerState


class SchedulerStateRepository:
    STATE_ID = 1

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def get_or_create(self) -> SchedulerState:
        state = self._session.get(
            SchedulerState,
            self.STATE_ID,
        )

        if state is not None:
            return state

        state = SchedulerState(
            id=self.STATE_ID,
            enabled=False,
            interval_seconds=300,
            consecutive_failures=0,
        )

        self._session.add(state)
        self._session.commit()
        self._session.refresh(state)

        return state

    def update(
        self,
        *,
        enabled: bool | None = None,
        interval_seconds: int | None = None,
    ) -> SchedulerState:
        state = self.get_or_create()

        if enabled is not None:
            state.enabled = enabled

        if interval_seconds is not None:
            if interval_seconds < 60:
                raise ValueError(
                    "Scheduler interval must be at "
                    "least 60 seconds."
                )

            state.interval_seconds = interval_seconds

        now = datetime.now(timezone.utc)
        state.updated_at = now

        if state.enabled:
            state.next_run_at = (
                now
                + timedelta(
                    seconds=state.interval_seconds
                )
            )
        else:
            state.next_run_at = None

        self._session.add(state)
        self._session.commit()
        self._session.refresh(state)

        return state

    def record_cycle(
        self,
        *,
        cycle_id: int,
        cycle_status: str,
        finished_at: datetime | None,
    ) -> SchedulerState:
        state = self.get_or_create()
        now = finished_at or datetime.now(
            timezone.utc
        )

        state.last_cycle_id = cycle_id
        state.last_run_at = now

        if cycle_status == "FAILED":
            state.consecutive_failures += 1
        else:
            state.consecutive_failures = 0

        if state.enabled:
            state.next_run_at = (
                now
                + timedelta(
                    seconds=state.interval_seconds
                )
            )
        else:
            state.next_run_at = None

        state.updated_at = datetime.now(
            timezone.utc
        )

        self._session.add(state)
        self._session.commit()
        self._session.refresh(state)

        return state
