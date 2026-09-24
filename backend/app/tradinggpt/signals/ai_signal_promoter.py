from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.signal_ai_review import SignalAIReview
from app.models.signal_discovery import SignalScanCandidate

from .ai_reviewer import BLOCKING_AI_RISK_FLAGS
from .generator import TradingSignalGenerator
from .repository import TradingSignalRepository
from .service import (
    DuplicateSignalError,
    TradingSignalService,
)


REQUIRED_TIMEFRAMES = frozenset(
    {
        "1H",
        "4H",
        "1D",
    }
)


class AISignalPromotionService:
    def __init__(
        self,
        *,
        db: Session,
        settings: Settings,
        generator: TradingSignalGenerator
        | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.generator = generator or (
            TradingSignalGenerator(
                TradingSignalService(
                    TradingSignalRepository(db)
                )
            )
        )

    def promote(
        self,
        *,
        candidate: SignalScanCandidate,
        review: SignalAIReview,
    ) -> dict[str, Any]:
        if candidate.signal_id is not None:
            return {
                "action": "ALREADY_PROMOTED",
                "candidate_id": int(candidate.id),
                "signal_id": int(candidate.signal_id),
            }

        if (
            review.status != "APPROVED"
            or review.verdict != "APPROVE"
        ):
            return self._blocked(
                candidate,
                "AI_REVIEW_NOT_APPROVED",
            )

        action = str(
            candidate.signal_action or ""
        ).strip().upper()
        trade_direction = str(
            candidate.trade_direction or ""
        ).strip().upper()
        requested_direction = str(
            review.requested_direction or ""
        ).strip().upper()
        verdict_direction = str(
            review.verdict_direction or ""
        ).strip().upper()

        directions = {
            action,
            trade_direction,
            requested_direction,
            verdict_direction,
        }

        if (
            action not in {"LONG", "SHORT"}
            or directions != {action}
        ):
            return self._blocked(
                candidate,
                "PROMOTION_DIRECTION_CONFLICT",
            )

        if str(
            candidate.risk_level or ""
        ).strip().upper() == "HIGH":
            return self._blocked(
                candidate,
                "PROMOTION_HIGH_RISK",
            )

        snapshot = (
            dict(candidate.snapshot)
            if isinstance(candidate.snapshot, dict)
            else {}
        )

        timeframe_directions = (
            snapshot.get("timeframe_directions")
        )

        if not isinstance(
            timeframe_directions,
            dict,
        ):
            return self._blocked(
                candidate,
                "PROMOTION_TIMEFRAMES_UNAVAILABLE",
            )

        normalized_timeframes = {
            str(key).strip().upper(): (
                str(value).strip().upper()
            )
            for key, value
            in timeframe_directions.items()
        }

        if not REQUIRED_TIMEFRAMES.issubset(
            normalized_timeframes
        ):
            return self._blocked(
                candidate,
                "PROMOTION_TIMEFRAMES_UNAVAILABLE",
            )

        if any(
            normalized_timeframes[timeframe]
            != action
            for timeframe in REQUIRED_TIMEFRAMES
        ):
            return self._blocked(
                candidate,
                "PROMOTION_TIMEFRAME_CONFLICT",
            )

        normalized_flags = {
            str(flag)
            .strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
            for flag in (review.risk_flags or [])
        }

        blocking_flags = (
            normalized_flags
            & (
                BLOCKING_AI_RISK_FLAGS
                | {"HIGH_RISK"}
            )
        )

        if blocking_flags:
            return {
                **self._blocked(
                    candidate,
                    "PROMOTION_BLOCKING_RISK",
                ),
                "blocking_risk_flags": sorted(
                    blocking_flags
                ),
            }

        promoted_payload = dict(snapshot)
        promoted_payload.update(
            {
                "recommendation": action,
                "signal_action": action,
                "trade_direction": action,
            }
        )

        request, rejection_reason = (
            self.generator._build_request(
                promoted_payload,
                generated_at=datetime.now(
                    timezone.utc
                ),
                min_confidence=Decimal(
                    str(
                        self.settings
                        .signal_ai_min_confidence
                    )
                ),
            )
        )

        if request is None:
            return self._blocked(
                candidate,
                (
                    "PROMOTION_REQUEST_REJECTED:"
                    f"{rejection_reason or 'UNKNOWN'}"
                ),
            )

        ai_reason = (
            "AI Review approved "
            f"{action} with confidence "
            f"{review.ai_confidence}."
        )
        rationale = str(
            review.rationale or ""
        ).strip()

        reasons = list(request.reasons[:18])
        reasons.append(ai_reason)

        if rationale:
            reasons.append(
                f"AI: {rationale}"[:500]
            )

        metadata = dict(
            request.metadata_payload
        )
        metadata["ai_review"] = {
            "review_id": int(review.id),
            "candidate_id": int(candidate.id),
            "status": review.status,
            "verdict": review.verdict,
            "requested_direction": (
                requested_direction
            ),
            "verdict_direction": (
                verdict_direction
            ),
            "confidence": (
                float(review.ai_confidence)
                if review.ai_confidence
                is not None
                else None
            ),
            "rationale": rationale,
            "risk_flags": list(
                review.risk_flags or []
            ),
            "promotion_policy": (
                "STRICT_ALIGNED_V1"
            ),
        }

        request = request.model_copy(
            update={
                "reasons": reasons[:20],
                "metadata_payload": metadata,
                "source": "AI_REVIEW",
            }
        )

        try:
            signal = (
                self.generator.service.create(
                    request
                )
            )
        except DuplicateSignalError as exc:
            candidate.signal_id = (
                exc.existing_signal_id
            )
            self._record_promotion(
                candidate,
                action="DUPLICATE",
                signal_id=exc.existing_signal_id,
                review_id=int(review.id),
            )
            self.db.commit()

            return {
                "action": "DUPLICATE",
                "candidate_id": int(candidate.id),
                "review_id": int(review.id),
                "signal_id": (
                    exc.existing_signal_id
                ),
            }

        candidate.signal_id = int(signal.id)
        candidate.outcome = "PROMOTED"

        self._record_promotion(
            candidate,
            action="CREATED",
            signal_id=int(signal.id),
            review_id=int(review.id),
        )
        self.db.commit()

        return {
            "action": "CREATED",
            "candidate_id": int(candidate.id),
            "review_id": int(review.id),
            "signal_id": int(signal.id),
        }

    @staticmethod
    def _record_promotion(
        candidate: SignalScanCandidate,
        *,
        action: str,
        signal_id: int,
        review_id: int,
    ) -> None:
        snapshot = (
            dict(candidate.snapshot)
            if isinstance(candidate.snapshot, dict)
            else {}
        )
        snapshot["ai_promotion"] = {
            "action": action,
            "signal_id": signal_id,
            "review_id": review_id,
            "policy": "STRICT_ALIGNED_V1",
        }
        candidate.snapshot = snapshot

    @staticmethod
    def _blocked(
        candidate: SignalScanCandidate,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "action": "BLOCKED",
            "candidate_id": int(candidate.id),
            "reason": reason,
        }
