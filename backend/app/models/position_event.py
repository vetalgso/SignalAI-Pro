from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PositionEvent(Base):
    __tablename__ = "position_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    position_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(48),
        index=True,
        nullable=False,
    )
    price: Mapped[float | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
