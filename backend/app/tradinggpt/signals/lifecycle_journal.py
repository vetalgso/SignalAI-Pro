"""Best-effort diagnostics in transactions independent of signal updates."""
from datetime import datetime, timezone
import logging
from time import monotonic
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.models.signal_lifecycle_cycle import SignalLifecycleCycle

logger = logging.getLogger(__name__)
WORKER_ID = str(uuid4())
COUNTERS = ("checked_signals", "updated_signals", "transition_count", "price_updates")


def safe_error_code(error: object) -> str:
    # Raw messages, exception names outside this allowlist and identifiers
    # must never become journal values or dynamic labels.
    if isinstance(error, SQLAlchemyError):
        return "DATABASE_ERROR"
    name = type(error).__name__ if isinstance(error, BaseException) else error
    if not isinstance(name, str):
        return "UNKNOWN_ERROR"
    if name in ("TimeoutError", "ReadTimeout", "ConnectTimeout", "PoolTimeout"):
        return "UPSTREAM_TIMEOUT"
    if name in ("ConnectionError", "ConnectError", "NetworkError", "RemoteProtocolError"):
        return "UPSTREAM_CONNECTION_ERROR"
    if name == "MarketDataError":
        return "MARKET_DATA_ERROR"
    if name in ("SQLAlchemyError", "OperationalError", "IntegrityError", "PendingRollbackError", "DBAPIError"):
        return "DATABASE_ERROR"
    if name in ("TypeError", "ValueError", "KeyError", "IndexError", "AttributeError", "InvalidOperation"):
        return "INVALID_LIFECYCLE_DATA"
    return "UNKNOWN_ERROR"


def result_summary(result: object) -> dict:
    if not isinstance(result, dict) or any(
        type(result.get(name)) is not int or not 0 <= result[name] <= 2147483647
        for name in COUNTERS
    ) or not isinstance(result.get("errors"), list):
        return {"status": "FAILED", "error_count": 1,
                "error_counts": {"INVALID_CYCLE_RESULT": 1}}
    counts: dict[str, int] = {}
    for item in result["errors"]:
        code = safe_error_code(item.get("error") if isinstance(item, dict) else None)
        counts[code] = counts.get(code, 0) + 1
    return {**{name: result[name] for name in COUNTERS},
            "status": "PARTIAL" if counts else "COMPLETED",
            "error_count": len(result["errors"]), "error_counts": counts}


class LifecycleJournal:
    def __init__(self, session_factory, interval_seconds: float):
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.cycle_id: int | None = None
        self.started_clock = monotonic()

    def begin(self) -> None:
        self.started_clock = monotonic()
        try:
            with self.session_factory() as db:
                row = SignalLifecycleCycle(worker_id=WORKER_ID, status="RUNNING",
                    started_at=datetime.now(timezone.utc),
                    poll_interval_seconds=self.interval_seconds, error_counts={})
                db.add(row)
                db.flush()
                cycle_id = row.id
                db.commit()
                self.cycle_id = cycle_id
        except SQLAlchemyError:
            logger.warning("Lifecycle journal begin failed; code=JOURNAL_WRITE_FAILED")

    def finish(self, values: dict) -> None:
        if self.cycle_id is None:
            return
        try:
            with self.session_factory() as db:
                db.execute(update(SignalLifecycleCycle).where(
                    SignalLifecycleCycle.id == self.cycle_id,
                    SignalLifecycleCycle.status == "RUNNING",
                ).values(**values, completed_at=datetime.now(timezone.utc),
                         duration_seconds=round(max(0.0, monotonic() - self.started_clock), 6)))
                db.commit()
        except SQLAlchemyError:
            logger.warning("Lifecycle journal finish failed; code=JOURNAL_WRITE_FAILED")

    def complete(self, result: object) -> None:
        values = result_summary(result)
        self.finish(values)
        if values["error_count"]:
            logger.warning("Lifecycle result contains errors; status=%s count=%s",
                           values["status"], values["error_count"])

    def fail(self, error: BaseException) -> None:
        self.finish({"status": "FAILED", "error_count": 1,
                     "error_counts": {safe_error_code(error): 1}})

    def cancel(self) -> None:
        self.finish({"status": "CANCELLED", "error_count": 1,
                     "error_counts": {"CYCLE_CANCELLED": 1}})
