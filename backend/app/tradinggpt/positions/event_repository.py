from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position_event import PositionEvent


class PositionEventRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        *,
        position_id: int,
        event_type: str,
        price: float | None,
        payload: dict[str, Any] | None = None,
    ) -> PositionEvent:
        event = PositionEvent(
            position_id=position_id,
            event_type=event_type,
            price=(
                Decimal(str(price))
                if price is not None
                else None
            ),
            payload=payload or {},
        )

        self._session.add(event)
        self._session.flush()

        return event

    def list_events(
        self,
        *,
        position_id: int | None = None,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[PositionEvent]:
        statement = select(PositionEvent)

        if position_id is not None:
            statement = statement.where(
                PositionEvent.position_id
                == position_id
            )

        if event_type is not None:
            statement = statement.where(
                PositionEvent.event_type
                == event_type.upper()
            )

        statement = statement.order_by(
            PositionEvent.id.desc()
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )
