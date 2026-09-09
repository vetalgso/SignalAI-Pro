from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.positions.event_repository import (
    PositionEventRepository,
)
from app.tradinggpt.positions.monitor import (
    PositionMonitorService,
)
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
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


def build_monitor(
    session: Session,
) -> tuple[
    PositionMonitorService,
    TradingPositionRepository,
    PositionEventRepository,
]:
    positions = TradingPositionRepository(
        session
    )
    events = PositionEventRepository(session)

    monitor = PositionMonitorService(
        position_repository=positions,
        event_repository=events,
    )

    return monitor, positions, events


def create_long(
    repository: TradingPositionRepository,
):
    return repository.create(
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
    )


def test_monitor_updates_unrealized_pnl() -> None:
    with build_session() as session:
        monitor, positions, events = (
            build_monitor(session)
        )
        position = create_long(positions)
        session.commit()

        result = monitor.monitor(
            prices={"BTCUSDT": 105.0}
        )

        session.refresh(position)

        assert result["updated_positions"] == 1
        assert float(
            position.unrealized_pnl
        ) == 5.0
        assert (
            events.list_events()[0].event_type
            == "PRICE_UPDATED"
        )


def test_monitor_triggers_tp1_and_break_even() -> None:
    with build_session() as session:
        monitor, positions, events = (
            build_monitor(session)
        )
        position = create_long(positions)
        session.commit()

        result = monitor.monitor(
            prices={"BTCUSDT": 110.0}
        )

        session.refresh(position)

        assert position.status == (
            "PARTIALLY_CLOSED"
        )
        assert float(
            position.remaining_quantity
        ) == 0.5
        assert float(position.stop_loss) == 100.0
        assert result["updated_positions"] == 1

        event_types = {
            event.event_type
            for event in events.list_events()
        }

        assert event_types == {
            "TAKE_PROFIT_1",
            "BREAK_EVEN",
        }


def test_monitor_triggers_tp2() -> None:
    with build_session() as session:
        monitor, positions, events = (
            build_monitor(session)
        )
        position = create_long(positions)
        session.commit()

        monitor.monitor(
            prices={"BTCUSDT": 110.0}
        )
        monitor.monitor(
            prices={"BTCUSDT": 120.0}
        )

        session.refresh(position)

        assert position.status == "CLOSED"
        assert float(position.realized_pnl) == 15.0
        assert (
            events.list_events()[0].event_type
            == "TAKE_PROFIT_2"
        )


def test_monitor_triggers_stop_loss() -> None:
    with build_session() as session:
        monitor, positions, events = (
            build_monitor(session)
        )
        position = create_long(positions)
        session.commit()

        monitor.monitor(
            prices={"BTCUSDT": 90.0}
        )

        session.refresh(position)

        assert position.status == "CLOSED"
        assert float(position.realized_pnl) == -10.0
        assert (
            events.list_events()[0].event_type
            == "STOP_LOSS"
        )


def test_monitor_reports_missing_price() -> None:
    with build_session() as session:
        monitor, positions, _ = (
            build_monitor(session)
        )
        create_long(positions)
        session.commit()

        result = monitor.monitor(
            prices={"ETHUSDT": 2000.0}
        )

        assert result["updated_positions"] == 0
        assert result["missing_symbols"] == [
            "BTCUSDT"
        ]


def test_monitor_rejects_invalid_price() -> None:
    with build_session() as session:
        monitor, _, _ = build_monitor(session)

        try:
            monitor.monitor(
                prices={"BTCUSDT": 0.0}
            )
        except ValueError as exc:
            assert (
                "must be greater than zero"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Invalid price was accepted."
            )
