from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.scheduler.payload_executor import (
    execute_persisted_scheduler_payload,
)
from app.tradinggpt.scheduler.payload_repository import (
    SchedulerPayloadRepository,
)
from app.tradinggpt.scheduler.payload_service import (
    SchedulerPayloadService,
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


def test_default_payload_is_not_configured() -> None:
    with build_session() as session:
        service = SchedulerPayloadService(
            SchedulerPayloadRepository(session)
        )

        payload = service.get()

        assert payload["configured"] is False
        assert (
            payload["runtime_risk_payload"]
            is None
        )
        assert payload["analysis_payload"] is None


def test_payload_is_singleton() -> None:
    with build_session() as session:
        repository = (
            SchedulerPayloadRepository(session)
        )

        first = repository.get_or_create()
        second = repository.get_or_create()

        assert first.id == 1
        assert second.id == 1


def test_repository_saves_payload() -> None:
    with build_session() as session:
        repository = (
            SchedulerPayloadRepository(session)
        )

        stored = repository.save(
            runtime_risk_payload={
                "equity": 10_000.0
            },
            analysis_payload={
                "dry_run": True
            },
        )

        assert stored.configured is True
        assert stored.runtime_risk_payload[
            "equity"
        ] == 10_000.0
        assert stored.analysis_payload[
            "dry_run"
        ] is True


def test_clear_removes_payload() -> None:
    with build_session() as session:
        repository = (
            SchedulerPayloadRepository(session)
        )

        repository.save(
            runtime_risk_payload={"safe": True},
            analysis_payload={"dry_run": True},
        )
        cleared = repository.clear()

        assert cleared.configured is False
        assert (
            cleared.runtime_risk_payload is None
        )
        assert cleared.analysis_payload is None


def test_executor_returns_none_without_payload() -> None:
    with build_session() as session:
        result = (
            execute_persisted_scheduler_payload(
                session
            )
        )

        assert result is None


def test_repository_overwrites_existing_payload() -> None:
    with build_session() as session:
        repository = (
            SchedulerPayloadRepository(session)
        )

        first = repository.save(
            runtime_risk_payload={
                "version": 1
            },
            analysis_payload={
                "dry_run": True,
                "version": 1,
            },
        )
        second = repository.save(
            runtime_risk_payload={
                "version": 2
            },
            analysis_payload={
                "dry_run": True,
                "version": 2,
            },
        )

        assert first.id == second.id == 1
        assert second.runtime_risk_payload[
            "version"
        ] == 2
