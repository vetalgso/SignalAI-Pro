from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.tradinggpt.signals.ai_signal_promoter import (
    AISignalPromotionService,
)


class FakeDB:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class FakeRequest:
    def __init__(self) -> None:
        self.reasons = ["Technical alignment."]
        self.metadata_payload = {
            "scanner": {
                "ranking_score": 65,
            },
        }
        self.source = "MARKET_SCANNER"

    def model_copy(
        self,
        *,
        update,
    ):
        clone = FakeRequest()

        for key, value in update.items():
            setattr(clone, key, value)

        return clone


class FakeSignalService:
    def __init__(self) -> None:
        self.requests = []

    def create(self, request):
        self.requests.append(request)
        return SimpleNamespace(id=901)


class FakeGenerator:
    def __init__(self) -> None:
        self.service = FakeSignalService()
        self.payloads = []

    def _build_request(
        self,
        payload,
        *,
        generated_at,
        min_confidence,
    ):
        self.payloads.append(
            {
                "payload": payload,
                "generated_at": generated_at,
                "min_confidence": min_confidence,
            }
        )
        return FakeRequest(), None


def settings():
    return SimpleNamespace(
        signal_ai_min_confidence=45,
    )


def candidate(
    *,
    risk_level: str = "medium",
    timeframes=None,
):
    return SimpleNamespace(
        id=301,
        signal_id=None,
        signal_action="LONG",
        trade_direction="LONG",
        risk_level=risk_level,
        outcome="REJECTED",
        snapshot={
            "symbol": "BTCUSDT",
            "confidence": 55,
            "signal_action": "LONG",
            "trade_direction": "LONG",
            "recommendation": "WAIT",
            "timeframe_directions": (
                timeframes
                or {
                    "1H": "LONG",
                    "4H": "LONG",
                    "1D": "LONG",
                }
            ),
        },
    )


def review(*, risk_flags=None):
    return SimpleNamespace(
        id=2,
        status="APPROVED",
        verdict="APPROVE",
        requested_direction="LONG",
        verdict_direction="LONG",
        ai_confidence=Decimal("65"),
        rationale="Technical evidence confirms LONG.",
        risk_flags=risk_flags or [],
        completed_at=datetime.now(timezone.utc),
    )


def service():
    db = FakeDB()
    generator = FakeGenerator()

    return (
        AISignalPromotionService(
            db=db,
            settings=settings(),
            generator=generator,
        ),
        db,
        generator,
    )


def test_promotes_strict_aligned_candidate() -> None:
    promoter, db, generator = service()
    item = candidate()

    result = promoter.promote(
        candidate=item,
        review=review(),
    )

    assert result["action"] == "CREATED"
    assert result["signal_id"] == 901
    assert item.signal_id == 901
    assert item.outcome == "PROMOTED"
    assert db.commits == 1

    built = generator.payloads[0]
    assert (
        built["payload"]["recommendation"]
        == "LONG"
    )
    assert built["min_confidence"] == Decimal(
        "45"
    )

    request = generator.service.requests[0]
    assert request.source == "AI_REVIEW"
    assert (
        request.metadata_payload["ai_review"]
        ["promotion_policy"]
        == "STRICT_ALIGNED_V1"
    )


def test_blocks_high_risk_candidate() -> None:
    promoter, db, generator = service()

    result = promoter.promote(
        candidate=candidate(
            risk_level="high"
        ),
        review=review(),
    )

    assert result == {
        "action": "BLOCKED",
        "candidate_id": 301,
        "reason": "PROMOTION_HIGH_RISK",
    }
    assert db.commits == 0
    assert generator.payloads == []


def test_blocks_timeframe_conflict() -> None:
    promoter, _, generator = service()

    result = promoter.promote(
        candidate=candidate(
            timeframes={
                "1H": "LONG",
                "4H": "SHORT",
                "1D": "LONG",
            }
        ),
        review=review(),
    )

    assert result["reason"] == (
        "PROMOTION_TIMEFRAME_CONFLICT"
    )
    assert generator.payloads == []


def test_blocks_direction_change() -> None:
    promoter, _, generator = service()
    item = candidate()
    item.trade_direction = "SHORT"

    result = promoter.promote(
        candidate=item,
        review=review(),
    )

    assert result["reason"] == (
        "PROMOTION_DIRECTION_CONFLICT"
    )
    assert generator.payloads == []


def test_blocks_normalized_ai_risk_flag() -> None:
    promoter, _, generator = service()

    result = promoter.promote(
        candidate=candidate(),
        review=review(
            risk_flags=[
                "stale market data",
            ]
        ),
    )

    assert result["reason"] == (
        "PROMOTION_BLOCKING_RISK"
    )
    assert result["blocking_risk_flags"] == [
        "STALE_MARKET_DATA"
    ]
    assert generator.payloads == []


def test_existing_signal_is_idempotent() -> None:
    promoter, db, generator = service()
    item = candidate()
    item.signal_id = 777

    result = promoter.promote(
        candidate=item,
        review=review(),
    )

    assert result == {
        "action": "ALREADY_PROMOTED",
        "candidate_id": 301,
        "signal_id": 777,
    }
    assert db.commits == 0
    assert generator.payloads == []
