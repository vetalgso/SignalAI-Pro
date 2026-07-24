from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal import Signal
from app.schemas.signal import SignalCreate, SignalRead

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("", response_model=list[SignalRead])
def list_signals(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Signal]:
    statement = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=SignalRead, status_code=status.HTTP_201_CREATED)
def create_signal(payload: SignalCreate, db: Session = Depends(get_db)) -> Signal:
    signal = Signal(**payload.model_dump())
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@router.get("/{signal_id}", response_model=SignalRead)
def get_signal(signal_id: int, db: Session = Depends(get_db)) -> Signal:
    signal = db.get(Signal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
