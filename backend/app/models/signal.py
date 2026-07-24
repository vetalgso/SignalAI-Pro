from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    strategy: Mapped[str] = mapped_column(String(80))
    side: Mapped[str] = mapped_column(String(5))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    take_profit: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
