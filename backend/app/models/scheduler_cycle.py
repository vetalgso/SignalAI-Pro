from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SchedulerCycle(Base):
    __tablename__ = "scheduler_cycles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="STARTED",
    )
    dry_run: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    risk_payload: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_payload: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
