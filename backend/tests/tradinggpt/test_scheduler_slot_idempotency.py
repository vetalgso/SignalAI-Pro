from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.tradinggpt.scheduler.slot_idempotency import (
    SCHEDULER_SLOT_KEY_PREFIX,
    build_scheduler_slot_idempotency_key,
    resolve_due_scheduler_slot,
)


def test_without_slot_preserves_provided_key() -> None:
    result = build_scheduler_slot_idempotency_key(
        analysis_payload={
            "idempotency_key": "manual-key",
            "dry_run": True,
        },
        scheduled_for=None,
    )

    assert result == "manual-key"


def test_without_slot_preserves_missing_key() -> None:
    result = build_scheduler_slot_idempotency_key(
        analysis_payload={
            "dry_run": True,
        },
        scheduled_for=None,
    )

    assert result is None


def test_same_slot_and_payload_produce_same_key() -> None:
    slot = datetime(
        2026,
        8,
        3,
        12,
        45,
        0,
        123456,
        tzinfo=timezone.utc,
    )
    payload = {
        "idempotency_key": "recurring-base",
        "dry_run": True,
        "symbol": "BTCUSDT",
    }

    first = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=slot,
    )
    second = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=slot,
    )

    assert first == second
    assert first is not None
    assert first.startswith(
        SCHEDULER_SLOT_KEY_PREFIX
    )
    assert len(first) <= 128


def test_different_slots_produce_different_keys() -> None:
    first_slot = datetime(
        2026,
        8,
        3,
        12,
        45,
        tzinfo=timezone.utc,
    )
    second_slot = (
        first_slot + timedelta(seconds=60)
    )
    payload = {
        "idempotency_key": "recurring-base",
        "dry_run": True,
    }

    first = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=first_slot,
    )
    second = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=second_slot,
    )

    assert first != second


def test_payload_change_changes_slot_key() -> None:
    slot = datetime(
        2026,
        8,
        3,
        12,
        45,
        tzinfo=timezone.utc,
    )

    first = build_scheduler_slot_idempotency_key(
        analysis_payload={
            "dry_run": True,
            "symbol": "BTCUSDT",
        },
        scheduled_for=slot,
    )
    second = build_scheduler_slot_idempotency_key(
        analysis_payload={
            "dry_run": True,
            "symbol": "ETHUSDT",
        },
        scheduled_for=slot,
    )

    assert first != second


def test_naive_and_aware_utc_slots_match() -> None:
    naive = datetime(
        2026,
        8,
        3,
        12,
        45,
        0,
    )
    aware = naive.replace(
        tzinfo=timezone.utc
    )
    payload = {
        "dry_run": True,
        "symbol": "BTCUSDT",
    }

    naive_key = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=naive,
    )
    aware_key = build_scheduler_slot_idempotency_key(
        analysis_payload=payload,
        scheduled_for=aware,
    )

    assert naive_key == aware_key


def test_resolve_due_scheduler_slot() -> None:
    now = datetime(
        2026,
        8,
        3,
        12,
        45,
        tzinfo=timezone.utc,
    )
    future = now + timedelta(seconds=1)
    past = now - timedelta(seconds=1)

    assert (
        resolve_due_scheduler_slot(
            next_run_at=None,
            now=now,
        )
        is None
    )
    assert (
        resolve_due_scheduler_slot(
            next_run_at=future,
            now=now,
        )
        is None
    )
    assert (
        resolve_due_scheduler_slot(
            next_run_at=now,
            now=now,
        )
        == now
    )
    assert (
        resolve_due_scheduler_slot(
            next_run_at=past,
            now=now,
        )
        == past
    )
