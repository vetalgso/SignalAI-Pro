"""Read-only cohort report of recorded signal lifecycle outcomes, not trade PnL."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.trading_signal import TradingSignal, TradingSignalEvent

router = APIRouter()
OPEN = ("ACTIVE", "ENTRY_REACHED", "TP1_REACHED", "TP2_REACHED")
TERMINAL = ("TP3_REACHED", "STOPPED", "EXPIRED", "CANCELLED")
DIMENSIONS = ("source", "exchange", "market_type", "symbol", "side", "timeframe", "strategy")


class Counts(BaseModel):
    total: int = 0
    open: int = 0
    terminal: int = 0
    unknown_status: int = 0
    entered: int = 0
    tp1: int = 0
    tp2: int = 0
    tp3: int = 0
    stopped: int = 0
    expired: int = 0
    cancelled: int = 0
    without_events: int = 0
    manual_transitions: int = 0


class QualityGroup(Counts):
    source: str
    exchange: str
    market_type: str
    symbol: str
    side: str
    timeframe: str
    strategy: str


class QualityReport(BaseModel):
    generated_from: datetime
    as_of: datetime
    source: str
    summary: Counts
    groups: list[QualityGroup]
    total_groups: int
    limit: int
    offset: int


def build_quality_report(db: Session, *, days: int, source: str,
                         limit: int, offset: int, now: datetime) -> QualityReport:
    start = now - timedelta(days=days)
    signal = TradingSignal
    event = TradingSignalEvent
    cohort = [signal.generated_at >= start, signal.generated_at <= now]
    if source != "ALL":
        cohort.append(signal.source == source)

    # Aggregate events before joining signals: repeated events must not inflate
    # the number of signals reaching a milestone. Do not infer optional TP2
    # from TP3, or erase TP1 when a later event closes the signal at its stop.
    milestones = {"entry": "ENTRY_REACHED", "tp1": "TP1_REACHED",
                  "tp2": "TP2_REACHED", "tp3": "TP3_REACHED"}
    history = (
        select(event.signal_id, func.count(event.id).label("events"),
               *[func.max(case((event.to_status == status, 1), else_=0)).label(name)
                 for name, status in milestones.items()],
               func.max(case((event.event_type == "STATUS_CHANGED", 1), else_=0)).label("manual"))
        .join(signal, signal.id == event.signal_id)
        .where(*cohort, event.created_at <= now)
        .group_by(event.signal_id).subquery()
    )

    def count_if(condition, name):
        return func.sum(case((condition, 1), else_=0)).label(name)

    dimensions = [getattr(signal, name) for name in DIMENSIONS]
    statement = (
        select(*dimensions, func.count(signal.id).label("total"),
               count_if(signal.status.in_(OPEN), "open"),
               count_if(signal.status.in_(TERMINAL), "terminal"),
               count_if(signal.status.not_in(OPEN + TERMINAL), "unknown_status"),
               count_if((history.c.entry == 1) | (signal.entry_reached_at <= now), "entered"),
               *[count_if(getattr(history.c, name) == 1, name) for name in ("tp1", "tp2", "tp3")],
               count_if(signal.status == "STOPPED", "stopped"),
               count_if(signal.status == "EXPIRED", "expired"),
               count_if(signal.status == "CANCELLED", "cancelled"),
               count_if(history.c.events.is_(None), "without_events"),
               count_if(history.c.manual == 1, "manual_transitions"))
        .outerjoin(history, history.c.signal_id == signal.id)
        .where(*cohort).group_by(*dimensions).order_by(*dimensions)
    )
    # Both totals and paged groups come from this one database statement.
    groups = [QualityGroup(**dict(row)) for row in db.execute(statement).mappings()]
    summary = Counts(**{name: sum(getattr(group, name) for group in groups)
                        for name in Counts.model_fields})
    return QualityReport(generated_from=start, as_of=now, source=source,
                         summary=summary, groups=groups[offset:offset + limit],
                         total_groups=len(groups), limit=limit, offset=offset)


@router.get("/quality", response_model=QualityReport)
def get_signal_quality(
    days: int = Query(default=30, ge=1, le=365),
    source: Literal["AI_REVIEW", "SCANNER", "ALL"] = Query(default="AI_REVIEW"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> QualityReport:
    return build_quality_report(db, days=days, source=source, limit=limit,
                                offset=offset, now=datetime.now(timezone.utc))
