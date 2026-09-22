from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal_discovery import SignalScanCandidate, SignalScanRun
from app.tradinggpt.risk_assessment import RiskAssessment, read_risk_assessment
from app.tradinggpt.quality_details import QualityBreakdown, read_quality_breakdown
from .ai_admission import AdmissionDecision, read_admission

router = APIRouter()


class AdmissionRun(BaseModel):
    id: int
    completed_at: datetime
    scanned_assets: int


class AdmissionRow(BaseModel):
    candidate_id: int
    symbol: str
    decision: AdmissionDecision | None
    quality: QualityBreakdown | None = None
    risk: RiskAssessment | None = None


class AdmissionPage(BaseModel):
    run: AdmissionRun | None
    items: list[AdmissionRow]
    total: int
    limit: int
    offset: int
    reason_counts: dict[str, int]
    not_recorded_count: int


@router.get("/ai-admission", response_model=AdmissionPage)
def list_ai_admission(
    run_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AdmissionPage:
    run = (db.get(SignalScanRun, run_id) if run_id is not None else db.scalar(
        select(SignalScanRun).order_by(SignalScanRun.id.desc()).limit(1)
    ))
    if run is None:
        if run_id is not None:
            raise HTTPException(status_code=404, detail="Scan run not found")
        return AdmissionPage(run=None, items=[], total=0, limit=limit, offset=offset,
                             reason_counts={}, not_recorded_count=0)

    # One scan's candidates only; totals are for the whole scan, not this page.
    candidates = db.scalars(select(SignalScanCandidate).where(
        SignalScanCandidate.run_id == run.id,
        SignalScanCandidate.rejection_reason == "RECOMMENDATION_CONFLICT",
    ).order_by(SignalScanCandidate.id)).all()
    rows = [AdmissionRow(candidate_id=c.id, symbol=c.symbol,
                         decision=read_admission(c.snapshot),
                         quality=read_quality_breakdown(c.snapshot),
                         risk=read_risk_assessment(c.snapshot, c.risk_level)) for c in candidates]
    return AdmissionPage(
        run=AdmissionRun(id=run.id, completed_at=run.completed_at,
                         scanned_assets=run.scanned_assets),
        items=rows[offset:offset + limit], total=len(rows), limit=limit, offset=offset,
        reason_counts=dict(Counter(row.decision.reason for row in rows if row.decision)),
        not_recorded_count=sum(row.decision is None for row in rows),
    )
