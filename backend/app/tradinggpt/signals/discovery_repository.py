from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.signal_discovery import (
    SignalScanCandidate,
    SignalScanRun,
)


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None


def _json_safe(value: object) -> Any:
    return json.loads(
        json.dumps(value, default=str)
    )
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class SignalDiscoveryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_completed_scan(
        self,
        *,
        scan_result: dict[str, Any],
        persistence_result: dict[str, Any],
        risk_level: str,
        minimum_confidence: Decimal,
        requested_limit: int,
        started_at: datetime,
        completed_at: datetime,
        suppressed_symbols: set[str] | None = None,
    ) -> SignalScanRun:
        suppressed = {
            symbol.upper() for symbol in (suppressed_symbols or set())
        }
        rejection_reasons = dict(
            persistence_result.get("rejection_reasons", {})
        )
        if suppressed:
            rejection_reasons["ACTIVE_SIGNAL"] = len(suppressed)

        run = SignalScanRun(
            status="COMPLETED",
            universe_source=str(
                scan_result.get("universe_source", "UNKNOWN")
            ),
            risk_level=risk_level.upper(),
            minimum_confidence=minimum_confidence,
            requested_limit=requested_limit,
            universe_assets=_json_safe(
                scan_result.get("universe_assets", [])
            ),
            scanned_assets=int(scan_result.get("scanned_assets", 0)),
            successful_assets=int(
                scan_result.get("successful_assets", 0)
            ),
            failed_assets=int(scan_result.get("failed_assets", 0)),
            opportunities_found=int(
                persistence_result.get("opportunities_found", 0)
            ),
            created_count=int(
                persistence_result.get("created_count", 0)
            ),
            duplicate_count=int(
                persistence_result.get("duplicate_count", 0)
            ),
            skipped_count=int(
                persistence_result.get("skipped_count", 0)
            ) + len(suppressed),
            rejection_reasons=rejection_reasons,
            scanner_errors=_json_safe(scan_result.get("errors", [])),
            started_at=started_at,
            completed_at=completed_at,
        )
        self.db.add(run)
        self.db.flush()

        evaluations = {
            str(item.get("symbol", "UNKNOWN")).upper(): item
            for item in persistence_result.get("evaluations", [])
            if isinstance(item, dict)
        }

        for raw in scan_result.get("candidates", []):
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol", "UNKNOWN")).upper()
            evaluation = evaluations.get(symbol, {})
            if symbol in suppressed:
                outcome = "REJECTED"
                reason = "ACTIVE_SIGNAL"
                signal_id = None
            else:
                outcome = str(evaluation.get("outcome", "REJECTED"))
                reason = evaluation.get("reason") or "NOT_ACTIONABLE"
                signal_id = evaluation.get("signal_id")
                if outcome in {"CREATED", "DUPLICATE"}:
                    reason = None

            candidate = SignalScanCandidate(
                run_id=run.id,
                symbol=symbol,
                asset=str(raw.get("asset", symbol.removesuffix("USDT"))),
                outcome=outcome,
                rejection_reason=(str(reason) if reason else None),
                signal_id=(int(signal_id) if signal_id is not None else None),
                recommendation=(
                    str(raw.get("recommendation"))
                    if raw.get("recommendation") is not None
                    else None
                ),
                signal_action=(
                    str(raw.get("signal_action"))
                    if raw.get("signal_action") is not None
                    else None
                ),
                trade_direction=(
                    str(raw.get("trade_direction"))
                    if raw.get("trade_direction") is not None
                    else None
                ),
                confidence=_decimal_or_none(raw.get("confidence")),
                risk_level=(
                    str(raw.get("risk"))
                    if raw.get("risk") is not None
                    else None
                ),
                ranking_score=_decimal_or_none(raw.get("ranking_score")),
                snapshot=_json_safe(raw),
            )
            self.db.add(candidate)

        candidate_symbols = {
            str(item.get("symbol", "UNKNOWN")).upper()
            for item in scan_result.get("candidates", [])
            if isinstance(item, dict)
        }
        for error in scan_result.get("errors", []):
            if not isinstance(error, dict):
                continue
            asset = str(error.get("asset", "UNKNOWN")).upper()
            symbol = f"{asset}USDT"
            if symbol in candidate_symbols:
                continue
            self.db.add(
                SignalScanCandidate(
                    run_id=run.id,
                    symbol=symbol,
                    asset=asset,
                    outcome="ANALYSIS_FAILED",
                    rejection_reason=str(error.get("error", "UNKNOWN")),
                    snapshot=_json_safe(error),
                )
            )

        self.db.commit()
        self.db.refresh(run)
        return run
