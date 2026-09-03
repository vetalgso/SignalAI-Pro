from __future__ import annotations

import asyncio
from decimal import Decimal

from app.core.config import settings
from app.database.session import (
    SessionLocal,
    engine,
)
from app.tradinggpt.facade import tradinggpt
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoop,
)
from app.tradinggpt.scheduler.distributed_lock import (
    PostgresAdvisorySchedulerLock,
)

from .generator import TradingSignalGenerator
from .repository import TradingSignalRepository
from .service import TradingSignalService


ALLOWED_RISK_LEVELS = {
    "low",
    "medium",
    "high",
}


def run_signal_scanner_background_tick(
) -> dict[str, object]:
    if not (
        settings
        .signal_scanner_background_enabled
    ):
        return {
            "action": "SKIPPED_DISABLED",
            "reason": (
                "Periodic signal scanner "
                "is disabled."
            ),
        }

    risk_level = (
        settings
        .signal_scanner_risk_level
        .strip()
        .lower()
    )

    if risk_level not in ALLOWED_RISK_LEVELS:
        return {
            "action": "FAILED",
            "reason": (
                "Invalid periodic scanner "
                "risk level."
            ),
        }

    distributed_lock = (
        PostgresAdvisorySchedulerLock(
            engine=engine,
            lock_key=(
                settings
                .signal_scanner_advisory_lock_key
            ),
        )
    )
    acquired = False

    try:
        acquired = (
            distributed_lock.try_acquire()
        )

        if not acquired:
            return {
                "action": "SKIPPED_LOCKED",
                "reason": (
                    "Another periodic signal "
                    "scanner holds the lock."
                ),
            }

        scan_result = asyncio.run(
            tradinggpt.scan_market(
                assets=None,
                risk_level=risk_level,
                limit=(
                    settings
                    .signal_scanner_market_limit
                ),
            )
        )

        if not isinstance(
            scan_result,
            dict,
        ):
            raise TypeError(
                "Market scanner returned "
                "an invalid result."
            )

        raw_opportunities = (
            scan_result.get(
                "opportunities",
                [],
            )
        )

        if not isinstance(
            raw_opportunities,
            list,
        ):
            raw_opportunities = []

        raw_candidates = scan_result.get(
            "candidates",
            raw_opportunities,
        )

        if not isinstance(raw_candidates, list):
            raw_candidates = raw_opportunities

        with SessionLocal() as session:
            repository = (
                TradingSignalRepository(
                    session
                )
            )

            active_symbols = {
                signal.symbol.upper()
                for signal
                in repository.list_trackable(
                    limit=500
                )
            }

            eligible = []
            active_signal_skips = 0
            actionable_symbols = {
                str(item.get("symbol", "")).upper()
                for item in raw_opportunities
                if isinstance(item, dict)
            }

            for opportunity in raw_candidates:
                if not isinstance(
                    opportunity,
                    dict,
                ):
                    eligible.append(
                        opportunity
                    )
                    continue

                symbol = str(
                    opportunity.get(
                        "symbol",
                        "",
                    )
                ).upper()

                if (
                    symbol in active_symbols
                    and symbol in actionable_symbols
                ):
                    active_signal_skips += 1
                    continue

                eligible.append(opportunity)

            filtered_scan = dict(
                scan_result
            )
            filtered_scan[
                "candidates"
            ] = eligible
            filtered_scan[
                "opportunities"
            ] = [
                item
                for item in raw_opportunities
                if not (
                    isinstance(item, dict)
                    and str(item.get("symbol", "")).upper()
                    in active_symbols
                )
            ]

            result = TradingSignalGenerator(
                TradingSignalService(
                    repository
                )
            ).persist_scan(
                scan_result=filtered_scan,
                min_confidence=Decimal(
                    str(
                        settings
                        .signal_scanner_min_confidence
                    )
                ),
            )

            created_signal_ids = [
                int(signal.id)
                for signal
                in result["created"]
            ]

        return {
            "action": "COMPLETED",
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
                raw_opportunities
            ),
            "eligible_opportunities": len(
                filtered_scan["opportunities"]
            ),
            "active_signal_skips": (
                active_signal_skips
            ),
            "created_count": int(
                result["created_count"]
            ),
            "duplicate_count": int(
                result["duplicate_count"]
            ),
            "skipped_count": (
                int(result["skipped_count"])
                + active_signal_skips
            ),
            "created_signal_ids": (
                created_signal_ids
            ),
            "rejection_reasons": {
                **result.get("rejection_reasons", {}),
                **(
                    {"ACTIVE_SIGNAL": active_signal_skips}
                    if active_signal_skips
                    else {}
                ),
            },
        }
    finally:
        if acquired:
            distributed_lock.release()


signal_scanner_background_loop = (
    SchedulerBackgroundLoop(
        tick_callback=(
            run_signal_scanner_background_tick
        ),
        poll_interval_seconds=(
            settings
            .signal_scanner_interval_seconds
        ),
        task_name=(
            "tradinggpt-periodic-"
            "signal-scanner-loop"
        ),
        failure_actions=frozenset(
            {"FAILED"}
        ),
    )
)
