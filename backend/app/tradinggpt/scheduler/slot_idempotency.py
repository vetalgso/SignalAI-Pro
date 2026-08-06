from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


SCHEDULER_SLOT_KEY_PREFIX = "scheduler-slot-"


def build_scheduler_slot_idempotency_key(
    *,
    analysis_payload: Mapping[str, Any],
    scheduled_for: datetime | None,
) -> str | None:
    """
    Build one deterministic idempotency key per
    scheduled execution slot.

    The same payload and scheduled slot always produce
    the same key. A later slot produces a different key.

    Without a scheduled slot, the persisted key is
    preserved so manual execution keeps its existing
    behaviour.
    """

    if scheduled_for is None:
        existing_key = analysis_payload.get(
            "idempotency_key"
        )

        if existing_key is None:
            return None

        if not isinstance(existing_key, str):
            raise TypeError(
                "Scheduler payload idempotency key "
                "must be a string or null."
            )

        return existing_key

    normalized_slot = _as_utc(scheduled_for)

    canonical_payload = json.dumps(
        {
            "scheduled_for": (
                normalized_slot
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            ),
            "analysis": dict(analysis_payload),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    digest = hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    return f"{SCHEDULER_SLOT_KEY_PREFIX}{digest}"


def resolve_due_scheduler_slot(
    *,
    next_run_at: datetime | None,
    now: datetime | None = None,
) -> datetime | None:
    """
    Return the scheduled slot only after it is due.

    This prevents an early force=True request from
    consuming the key reserved for a future automatic
    scheduler cycle.
    """

    if next_run_at is None:
        return None

    normalized_slot = _as_utc(next_run_at)
    normalized_now = _as_utc(
        now or datetime.now(timezone.utc)
    )

    if normalized_slot > normalized_now:
        return None

    return normalized_slot


def _as_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(timezone.utc)
