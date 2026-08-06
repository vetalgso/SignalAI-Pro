from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.trading_signal import (
    TradingSignal,
    TradingSignalEvent,
)


class TradingSignalRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get(
        self,
        signal_id: int,
    ) -> TradingSignal | None:
        return self.db.get(
            TradingSignal,
            signal_id,
        )

    def get_by_fingerprint(
        self,
        fingerprint: str,
    ) -> TradingSignal | None:
        statement = select(
            TradingSignal
        ).where(
            TradingSignal.fingerprint
            == fingerprint
        )

        return self.db.scalar(statement)

    def add(
        self,
        signal: TradingSignal,
    ) -> TradingSignal:
        self.db.add(signal)
        self.db.flush()
        return signal

    def add_event(
        self,
        *,
        signal_id: int,
        event_type: str,
        from_status: str | None,
        to_status: str,
        price: Decimal | None = None,
        note: str | None = None,
        payload: dict[str, object]
        | None = None,
    ) -> TradingSignalEvent:
        event = TradingSignalEvent(
            signal_id=signal_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            price=price,
            note=note,
            payload=payload or {},
        )

        self.db.add(event)
        self.db.flush()

        return event

    def list_events(
        self,
        signal_id: int,
    ) -> list[TradingSignalEvent]:
        statement = (
            select(TradingSignalEvent)
            .where(
                TradingSignalEvent.signal_id
                == signal_id
            )
            .order_by(
                TradingSignalEvent.created_at.asc(),
                TradingSignalEvent.id.asc(),
            )
        )

        return list(
            self.db.scalars(
                statement
            ).all()
        )

    def list_trackable(
        self,
        *,
        limit: int = 500,
    ) -> list[TradingSignal]:
        statement = (
            select(TradingSignal)
            .where(
                TradingSignal.status.in_(
                    (
                        "ACTIVE",
                        "ENTRY_REACHED",
                        "TP1_REACHED",
                        "TP2_REACHED",
                    )
                )
            )
            .order_by(
                TradingSignal.generated_at.asc(),
                TradingSignal.id.asc(),
            )
            .limit(limit)
        )

        return list(
            self.db.scalars(
                statement
            ).all()
        )

    def list(
        self,
        *,
        exchange: str | None,
        symbol: str | None,
        timeframe: str | None,
        side: str | None,
        status: str | None,
        risk_level: str | None,
        min_confidence: Decimal | None,
        limit: int,
        offset: int,
    ) -> tuple[
        list[TradingSignal],
        int,
    ]:
        filters = []

        if exchange:
            filters.append(
                TradingSignal.exchange
                == exchange.upper()
            )

        if symbol:
            filters.append(
                TradingSignal.symbol
                == symbol.upper()
            )

        if timeframe:
            filters.append(
                TradingSignal.timeframe
                == timeframe.upper()
            )

        if side:
            filters.append(
                TradingSignal.side
                == side.upper()
            )

        if status:
            filters.append(
                TradingSignal.status
                == status.upper()
            )

        if risk_level:
            filters.append(
                TradingSignal.risk_level
                == risk_level.upper()
            )

        if min_confidence is not None:
            filters.append(
                TradingSignal.confidence
                >= min_confidence
            )

        statement = (
            select(TradingSignal)
            .where(*filters)
            .order_by(
                TradingSignal.generated_at.desc(),
                TradingSignal.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        count_statement = (
            select(
                func.count(
                    TradingSignal.id
                )
            )
            .where(*filters)
        )

        items = list(
            self.db.scalars(
                statement
            ).all()
        )
        total = int(
            self.db.scalar(
                count_statement
            )
            or 0
        )

        return items, total
