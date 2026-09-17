from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SignalLifecycleCycle(Base):
    __tablename__ = "signal_lifecycle_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    poll_interval_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    checked_signals: Mapped[int | None] = mapped_column(Integer)
    updated_signals: Mapped[int | None] = mapped_column(Integer)
    transition_count: Mapped[int | None] = mapped_column(Integer)
    price_updates: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int | None] = mapped_column(Integer)
    error_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
