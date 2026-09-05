from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal
from typing import Any

from app.models.trading_signal import (
    TradingSignal,
)

from .schemas import SignalCreateRequest
from .service import (
    DuplicateSignalError,
    TradingSignalService,
)


ACTIONABLE_RECOMMENDATIONS = {
    "LONG": {
        "LONG",
        "CAUTIOUS_BUY",
    },
    "SHORT": {
        "SHORT",
        "CAUTIOUS_SHORT",
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def decimal_value(
    value: object,
) -> Decimal:
    return Decimal(str(value))


class TradingSignalGenerator:
    def __init__(
        self,
        service: TradingSignalService,
    ) -> None:
        self.service = service

    def persist_scan(
        self,
        *,
        scan_result: dict[str, Any],
        min_confidence: Decimal,
    ) -> dict[str, Any]:
        opportunities = scan_result.get(
            "candidates",
            scan_result.get(
                "opportunities",
                [],
            ),
        )

        if not isinstance(
            opportunities,
            list,
        ):
            opportunities = []

        created: list[TradingSignal] = []
        duplicates: list[
            dict[str, object]
        ] = []
        skipped: list[
            dict[str, str]
        ] = []
        evaluations: list[
            dict[str, object]
        ] = []

        generated_at = utc_now()

        for raw_item in opportunities:
            if not isinstance(raw_item, dict):
                skipped.append(
                    {
                        "symbol": "UNKNOWN",
                        "reason": (
                            "INVALID_SCANNER_RESULT"
                        ),
                    }
                )
                evaluations.append(
                    {
                        "symbol": "UNKNOWN",
                        "outcome": "REJECTED",
                        "reason": "INVALID_SCANNER_RESULT",
                    }
                )
                continue

            symbol = str(
                raw_item.get(
                    "symbol",
                    "UNKNOWN",
                )
            ).upper()

            request, reason = (
                self._build_request(
                    raw_item,
                    generated_at=generated_at,
                    min_confidence=(
                        min_confidence
                    ),
                )
            )

            if request is None:
                skipped.append(
                    {
                        "symbol": symbol,
                        "reason": (
                            reason
                            or "NOT_ACTIONABLE"
                        ),
                    }
                )
                evaluations.append(
                    {
                        "symbol": symbol,
                        "outcome": "REJECTED",
                        "reason": (
                            reason
                            or "NOT_ACTIONABLE"
                        ),
                    }
                )
                continue

            try:
                signal = self.service.create(
                    request
                )
            except DuplicateSignalError as exc:
                duplicates.append(
                    {
                        "symbol": symbol,
                        "existing_signal_id": (
                            exc.existing_signal_id
                        ),
                    }
                )
                evaluations.append(
                    {
                        "symbol": symbol,
                        "outcome": "DUPLICATE",
                        "signal_id": (
                            exc.existing_signal_id
                        ),
                    }
                )
                continue

            created.append(signal)
            evaluations.append(
                {
                    "symbol": symbol,
                    "outcome": "CREATED",
                    "signal_id": int(signal.id),
                }
            )

        return {
            "universe_source": scan_result.get(
                "universe_source",
                "UNKNOWN",
            ),
            "universe_assets": scan_result.get(
                "universe_assets",
                [],
            ),
            "scanned_assets": int(
                scan_result.get(
                    "scanned_assets",
                    0,
                )
            ),
            "successful_assets": int(
                scan_result.get(
                    "successful_assets",
                    0,
                )
            ),
            "failed_assets": int(
                scan_result.get(
                    "failed_assets",
                    0,
                )
            ),
            "opportunities_found": len(
                scan_result.get(
                    "opportunities",
                    opportunities,
                )
            ),
            "evaluated_candidates": len(opportunities),
            "created_count": len(created),
            "duplicate_count": len(
                duplicates
            ),
            "skipped_count": len(skipped),
            "created": created,
            "duplicates": duplicates,
            "skipped": skipped,
            "scanner_errors": (
                scan_result.get(
                    "errors",
                    [],
                )
            ),
            "rejection_reasons": self._count_rejections(skipped),
            "evaluations": evaluations,
        }

    @staticmethod
    def _count_rejections(
        skipped: list[dict[str, str]],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        for item in skipped:
            reason = item.get("reason", "UNKNOWN")
            counts[reason] = counts.get(reason, 0) + 1

        return counts

    def _build_request(
        self,
        item: dict[str, Any],
        *,
        generated_at: datetime,
        min_confidence: Decimal,
    ) -> tuple[
        SignalCreateRequest | None,
        str | None,
    ]:
        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        action = str(
            item.get(
                "signal_action",
                "",
            )
        ).upper()

        direction = str(
            item.get(
                "trade_direction",
                "",
            )
        ).upper()

        recommendation = str(
            item.get(
                "recommendation",
                "",
            )
        ).upper()

        if action not in {
            "LONG",
            "SHORT",
        }:
            return (
                None,
                "NO_ACTIONABLE_TECHNICAL_SIGNAL",
            )

        if direction != action:
            return (
                None,
                "DIRECTION_CONFLICT",
            )

        if recommendation not in (
            ACTIONABLE_RECOMMENDATIONS[
                action
            ]
        ):
            return (
                None,
                "RECOMMENDATION_CONFLICT",
            )

        confidence = decimal_value(
            item.get(
                "confidence",
                0,
            )
        )

        if confidence < min_confidence:
            return (
                None,
                "LOW_CONFIDENCE",
            )

        levels = item.get(
            "signal_levels"
        )

        if not isinstance(levels, dict):
            return (
                None,
                "LEVELS_UNAVAILABLE",
            )

        required = {
            "entry",
            "stop_loss",
            "take_profit",
        }

        if not required.issubset(levels):
            return (
                None,
                "LEVELS_UNAVAILABLE",
            )

        try:
            entry = decimal_value(
                levels["entry"]
            )
            stop_loss = decimal_value(
                levels["stop_loss"]
            )
            raw_take_profit = decimal_value(
                levels["take_profit"]
            )
        except Exception:
            return (
                None,
                "INVALID_LEVELS",
            )

        if (
            entry <= 0
            or stop_loss <= 0
            or raw_take_profit <= 0
        ):
            return (
                None,
                "INVALID_LEVELS",
            )

        if action == "LONG":
            risk_distance = (
                entry - stop_loss
            )

            if risk_distance <= 0:
                return (
                    None,
                    "INVALID_LONG_LEVELS",
                )

            take_profit_1 = (
                entry + risk_distance
            )
            expected_take_profit_2 = (
                entry
                + risk_distance
                * Decimal("2")
            )
            take_profit_3 = (
                entry
                + risk_distance
                * Decimal("3")
            )

            take_profit_2 = (
                raw_take_profit
                if raw_take_profit
                > take_profit_1
                else expected_take_profit_2
            )
        else:
            risk_distance = (
                stop_loss - entry
            )

            if risk_distance <= 0:
                return (
                    None,
                    "INVALID_SHORT_LEVELS",
                )

            take_profit_1 = (
                entry - risk_distance
            )
            expected_take_profit_2 = (
                entry
                - risk_distance
                * Decimal("2")
            )
            take_profit_3 = (
                entry
                - risk_distance
                * Decimal("3")
            )

            take_profit_2 = (
                raw_take_profit
                if raw_take_profit
                < take_profit_1
                else expected_take_profit_2
            )

        if min(
            take_profit_1,
            take_profit_2,
            take_profit_3,
        ) <= 0:
            return (
                None,
                "INVALID_TARGETS",
            )

        reasons = [
            str(reason)
            for reason in item.get(
                "reasons",
                [],
            )
            if str(reason).strip()
        ]

        if not reasons:
            reasons = [
                (
                    "Scanner and technical "
                    "signal directions agree."
                )
            ]

        risk_level = str(
            item.get(
                "risk",
                "medium",
            )
        ).upper()

        if risk_level not in {
            "LOW",
            "MEDIUM",
            "HIGH",
        }:
            risk_level = "MEDIUM"

        strategy = str(
            item.get(
                "signal_strategy"
            )
            or "TECHNICAL_CONFLUENCE_V1"
        )

        current_price = item.get(
            "market_price"
        )

        metadata_payload = {
            "scanner": {
                "score": item.get(
                    "score"
                ),
                "opportunity_score": (
                    item.get(
                        "opportunity_score"
                    )
                ),
                "consensus_score": (
                    item.get(
                        "consensus_score"
                    )
                ),
                (
                    "timeframe_"
                    "consensus_score"
                ): item.get(
                    "timeframe_consensus_score"
                ),
                "ranking_score": item.get(
                    "ranking_score"
                ),
                "recommendation": (
                    recommendation
                ),
                "trade_direction": (
                    direction
                ),
                "trend_direction": (
                    item.get(
                        "trend_direction"
                    )
                ),
                "trade_style": item.get(
                    "trade_style"
                ),
                "timeframe_directions": (
                    item.get(
                        "timeframe_directions",
                        {},
                    )
                ),
                "quality_penalty": (
                    item.get(
                        "quality_penalty"
                    )
                ),
                "warnings": item.get(
                    "warnings",
                    [],
                ),
            },
            "technical_levels": {
                key: str(value)
                for key, value
                in levels.items()
            },
        }

        return (
            SignalCreateRequest(
                exchange="BINANCE",
                market_type="SPOT",
                symbol=symbol,
                timeframe="1H",
                side=action,
                strategy=strategy,
                confidence=confidence,
                risk_level=risk_level,
                entry_min=entry,
                entry_max=entry,
                stop_loss=stop_loss,
                take_profit_1=(
                    take_profit_1
                ),
                take_profit_2=(
                    take_profit_2
                ),
                take_profit_3=(
                    take_profit_3
                ),
                current_price=(
                    decimal_value(
                        current_price
                    )
                    if current_price
                    is not None
                    else entry
                ),
                reasons=reasons,
                metadata_payload=(
                    metadata_payload
                ),
                source="MARKET_SCANNER",
                generated_at=generated_at,
                expires_at=(
                    generated_at
                    + timedelta(hours=6)
                ),
            ),
            None,
        )
