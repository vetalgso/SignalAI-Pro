from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.models.scheduler_cycle import SchedulerCycle


class SchedulerCycleRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create_started(
        self,
        *,
        dry_run: bool = True,
    ) -> SchedulerCycle:
        cycle = SchedulerCycle(
            status="STARTED",
            dry_run=dry_run,
        )

        self._session.add(cycle)
        self._session.commit()
        self._session.refresh(cycle)

        return cycle

    def finish(
        self,
        *,
        cycle: SchedulerCycle,
        status: str,
        risk_payload: dict[str, Any] | None,
        execution_payload: (
            dict[str, Any] | None
        ),
        error_message: str | None = None,
    ) -> SchedulerCycle:
        cycle.status = status
        cycle.risk_payload = risk_payload
        cycle.execution_payload = (
            execution_payload
        )
        cycle.error_message = error_message
        cycle.finished_at = datetime.now(
            timezone.utc
        )

        self._session.add(cycle)
        self._session.commit()
        self._session.refresh(cycle)

        return cycle

    def get(
        self,
        cycle_id: int,
    ) -> SchedulerCycle | None:
        return self._session.get(
            SchedulerCycle,
            cycle_id,
        )

    def list_recent(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SchedulerCycle]:
        statement = select(SchedulerCycle)

        if status is not None:
            statement = statement.where(
                SchedulerCycle.status
                == status.upper()
            )

        statement = statement.order_by(
            SchedulerCycle.id.desc()
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )

    def count_by_status(
        self,
    ) -> dict[str, int]:
        statement = (
            select(
                SchedulerCycle.status,
                func.count(SchedulerCycle.id),
            )
            .group_by(SchedulerCycle.status)
            .order_by(SchedulerCycle.status)
        )

        rows = self._session.execute(
            statement
        ).all()

        return {
            str(status).upper(): int(count)
            for status, count in rows
        }
