from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.risk.models import (
    AccountRiskContext,
)
from app.tradinggpt.scheduler.journal_service import (
    JournaledSchedulerCycleService,
)
from app.tradinggpt.scheduler.repository import (
    SchedulerCycleRepository,
)
from app.tradinggpt.scheduler.service import (
    SafeSchedulerCycleService,
)


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def safe_account() -> AccountRiskContext:
    return AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=0.0,
        open_positions=1,
        current_exposure_value=1_000.0,
    )


def build_service(
    session: Session,
    callback,
) -> JournaledSchedulerCycleService:
    return JournaledSchedulerCycleService(
        cycle_service=SafeSchedulerCycleService(
            execute_callback=callback,
        ),
        repository=SchedulerCycleRepository(
            session
        ),
    )


def test_completed_cycle_is_persisted() -> None:
    with build_session() as session:
        service = build_service(
            session,
            lambda dry_run: {
                "action": "DRY_RUN",
                "dry_run": dry_run,
            },
        )

        result = service.run(
            account=safe_account()
        )
        stored = service.get(
            result["cycle_id"]
        )

        assert result["status"] == "COMPLETED"
        assert stored is not None
        assert stored["status"] == "COMPLETED"
        assert stored["execution"][
            "action"
        ] == "DRY_RUN"
        assert stored["finished_at"] is not None


def test_blocked_cycle_is_persisted() -> None:
    with build_session() as session:
        calls = 0

        def callback(dry_run: bool):
            nonlocal calls
            calls += 1
            return {}

        service = build_service(
            session,
            callback,
        )

        result = service.run(
            account=AccountRiskContext(
                equity=10_000.0,
                peak_equity=10_000.0,
                daily_pnl=-400.0,
                open_positions=1,
                current_exposure_value=1_000.0,
            )
        )

        assert result["status"] == "BLOCKED"
        assert calls == 0

        stored = service.get(
            result["cycle_id"]
        )
        assert stored is not None
        assert stored["risk"]["status"] == "DENY"


def test_failed_callback_is_persisted() -> None:
    with build_session() as session:
        def callback(dry_run: bool):
            raise RuntimeError(
                "Synthetic scheduler failure."
            )

        service = build_service(
            session,
            callback,
        )

        result = service.run(
            account=safe_account()
        )

        assert result["status"] == "FAILED"
        assert (
            "Synthetic scheduler failure"
            in result["error_message"]
        )

        stored = service.get(
            result["cycle_id"]
        )
        assert stored is not None
        assert stored["status"] == "FAILED"


def test_repository_filters_status() -> None:
    with build_session() as session:
        repository = SchedulerCycleRepository(
            session
        )

        first = repository.create_started()
        repository.finish(
            cycle=first,
            status="COMPLETED",
            risk_payload={"status": "ALLOW"},
            execution_payload={},
        )

        second = repository.create_started()
        repository.finish(
            cycle=second,
            status="BLOCKED",
            risk_payload={"status": "DENY"},
            execution_payload=None,
        )

        blocked = repository.list_recent(
            status="BLOCKED"
        )

        assert [item.id for item in blocked] == [
            second.id
        ]


def test_list_recent_returns_newest_first() -> None:
    with build_session() as session:
        repository = SchedulerCycleRepository(
            session
        )

        first = repository.create_started()
        second = repository.create_started()

        items = repository.list_recent()

        assert [item.id for item in items] == [
            second.id,
            first.id,
        ]
