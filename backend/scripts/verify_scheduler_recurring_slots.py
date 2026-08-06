from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from scripts.verify_scheduler_auto_dry_run import (
    api_request,
    build_payload,
    parse_datetime,
    restore_safe_state,
    scheduler_cycle_count_after,
    scheduler_cycle_max_id,
    trading_order_count,
)


TEST_INTERVAL_SECONDS = 60
EXECUTION_TIMEOUT_SECONDS = 150
SLOT_KEY_PREFIX = "scheduler-slot-"


def wait_for_two_cycles(
    *,
    baseline_cycle_id: int,
    first_due_at: datetime,
) -> datetime:
    deadline = (
        time.monotonic()
        + EXECUTION_TIMEOUT_SECONDS
    )
    second_due_at: datetime | None = None

    while time.monotonic() < deadline:
        count = scheduler_cycle_count_after(
            baseline_cycle_id
        )
        state = api_request(
            "GET",
            "/api/v3/scheduler/state",
        )

        if (
            count >= 1
            and second_due_at is None
            and state["next_run_at"] is not None
        ):
            second_due_at = parse_datetime(
                state["next_run_at"]
            )

            print()
            print(
                "First cycle completed; "
                "second slot due at:",
                second_due_at.isoformat(),
            )

        if count >= 2:
            if second_due_at is None:
                raise AssertionError(
                    "Second due time was not observed."
                )

            return second_due_at

        remaining_first = max(
            0,
            int(
                (
                    first_due_at
                    - datetime.now(timezone.utc)
                ).total_seconds()
            ),
        )

        print(
            "New cycles:",
            count,
            "| first due in:",
            remaining_first,
            "seconds",
            end="\r",
            flush=True,
        )

        time.sleep(1)

    raise TimeoutError(
        "Two recurring scheduler cycles were not "
        "completed before timeout."
    )


def main() -> None:
    print("=== 1. Проверяем исходную безопасность ===")

    initial_state = api_request(
        "GET",
        "/api/v3/scheduler/state",
    )
    initial_payload = api_request(
        "GET",
        "/api/v3/scheduler/payload",
    )
    initial_background = api_request(
        "GET",
        (
            "/api/v3/scheduler/"
            "runner/background/status"
        ),
    )

    assert initial_state["enabled"] is False
    assert initial_state["next_run_at"] is None
    assert initial_payload["configured"] is False
    assert initial_background["running"] is True
    assert initial_background["failed_ticks"] == 0
    assert initial_background["last_error"] is None

    original_interval = int(
        initial_state["interval_seconds"]
    )
    baseline_cycle_id = scheduler_cycle_max_id()

    base_key = (
        "scheduler-v322-recurring-"
        f"{uuid4().hex[:16]}"
    )

    print("Scheduler disabled: OK")
    print("Payload cleared: OK")
    print("Baseline cycle ID:", baseline_cycle_id)
    print("Base payload key:", base_key)

    try:
        print()
        print("=== 2. Сохраняем recurring PAPER payload ===")

        saved = api_request(
            "PUT",
            "/api/v3/scheduler/payload",
            build_payload(base_key),
        )

        assert saved["configured"] is True
        assert (
            saved["analysis_payload"]["dry_run"]
            is True
        )
        assert (
            saved["analysis_payload"]
            ["idempotency_key"]
            == base_key
        )
        assert (
            saved["analysis_payload"]
            ["order_routing"]["exchange"]
            == "PAPER"
        )

        print("Recurring payload configured: OK")

        print()
        print("=== 3. Включаем scheduler ===")

        enabled = api_request(
            "PATCH",
            "/api/v3/scheduler/state",
            {
                "enabled": True,
                "interval_seconds": (
                    TEST_INTERVAL_SECONDS
                ),
            },
        )

        assert enabled["enabled"] is True
        assert (
            enabled["interval_seconds"]
            == TEST_INTERVAL_SECONDS
        )
        assert enabled["next_run_at"] is not None

        first_due_at = parse_datetime(
            enabled["next_run_at"]
        )

        print(
            "First slot due at:",
            first_due_at.isoformat(),
        )

        print()
        print(
            "=== 4. Ожидаем два автоматических "
            "интервала ==="
        )

        second_due_at = wait_for_two_cycles(
            baseline_cycle_id=baseline_cycle_id,
            first_due_at=first_due_at,
        )

        print()
        print("Two automatic cycles observed: OK")

        print()
        print("=== 5. Немедленно выключаем scheduler ===")

        disabled = api_request(
            "PATCH",
            "/api/v3/scheduler/state",
            {"enabled": False},
        )

        assert disabled["enabled"] is False
        assert disabled["next_run_at"] is None

        print("Scheduler disabled: OK")

        print()
        print("=== 6. Получаем два новых cycle ===")

        recent = api_request(
            "GET",
            "/api/v3/scheduler/cycles?limit=20",
        )

        new_cycles = sorted(
            (
                cycle
                for cycle in recent
                if int(cycle["cycle_id"])
                > baseline_cycle_id
            ),
            key=lambda item: int(
                item["cycle_id"]
            ),
        )

        assert len(new_cycles) == 2, new_cycles

        first_cycle, second_cycle = new_cycles

        print(
            "Cycle IDs:",
            first_cycle["cycle_id"],
            second_cycle["cycle_id"],
        )

        print()
        print("=== 7. Проверяем результаты cycles ===")

        slot_keys: list[str] = []

        for index, cycle in enumerate(
            new_cycles,
            start=1,
        ):
            assert cycle["status"] == "COMPLETED", cycle
            assert cycle["dry_run"] is True, cycle
            assert cycle["error_message"] is None, cycle
            assert cycle["risk"]["status"] == "ALLOW", cycle

            execution = cycle["execution"]
            assert execution["action"] == "DRY_RUN", execution
            assert execution["reason"] is None, execution

            journal = execution["journal"]

            assert journal["replayed"] is False, journal
            assert journal["dry_run"] is True, journal
            assert journal["simulated"] is True, journal
            assert journal["exchange"] == "PAPER", journal
            assert journal["market_type"] == "SPOT", journal
            assert journal["symbol"] == "BTCUSDT", journal
            assert journal["status"] == "DRY_RUN", journal
            assert journal["client_order_id"] is None, journal
            assert journal["exchange_order_id"] is None, journal
            assert float(
                journal["filled_quantity"]
            ) == 0.0

            slot_key = str(
                journal["idempotency_key"]
            )

            assert slot_key.startswith(
                SLOT_KEY_PREFIX
            ), slot_key
            assert len(slot_key) <= 128

            slot_keys.append(slot_key)

            print(
                f"Cycle {index}:",
                cycle["cycle_id"],
                slot_key,
            )

        assert slot_keys[0] != slot_keys[1], slot_keys

        first_started_at = parse_datetime(
            first_cycle["started_at"]
        )
        second_started_at = parse_datetime(
            second_cycle["started_at"]
        )

        assert first_started_at >= first_due_at, {
            "started": first_started_at,
            "due": first_due_at,
        }
        assert second_started_at >= second_due_at, {
            "started": second_started_at,
            "due": second_due_at,
        }

        print("Both cycles COMPLETED: OK")
        print("Both actions DRY_RUN: OK")
        print("Both journals replayed=false: OK")
        print("Slot keys are different: OK")
        print("Both cycles started after due time: OK")

        print()
        print("=== 8. Проверяем order journal ===")

        assert trading_order_count(
            slot_keys[0]
        ) == 1
        assert trading_order_count(
            slot_keys[1]
        ) == 1

        # The original persisted key must not be used
        # for a due automatic slot.
        assert trading_order_count(base_key) == 0

        assert scheduler_cycle_count_after(
            baseline_cycle_id
        ) == 2

        print("First slot order count: 1")
        print("Second slot order count: 1")
        print("Base key order count: 0")
        print("New scheduler cycles: 2")

        print()
        print(
            "=== 9. Проверяем отсутствие "
            "третьего cycle ==="
        )

        time.sleep(10)

        assert scheduler_cycle_count_after(
            baseline_cycle_id
        ) == 2
        assert trading_order_count(
            slot_keys[0]
        ) == 1
        assert trading_order_count(
            slot_keys[1]
        ) == 1

        background = api_request(
            "GET",
            (
                "/api/v3/scheduler/"
                "runner/background/status"
            ),
        )

        assert background["running"] is True
        assert background["failed_ticks"] == 0
        assert background["last_error"] is None

        print("No third scheduler cycle: OK")
        print("No duplicate first order: OK")
        print("No duplicate second order: OK")
        print("Background loop healthy: OK")

    finally:
        restore_safe_state(original_interval)

    print()
    print("=== 10. Финальная безопасность ===")

    final_state = api_request(
        "GET",
        "/api/v3/scheduler/state",
    )
    final_payload = api_request(
        "GET",
        "/api/v3/scheduler/payload",
    )

    assert final_state["enabled"] is False
    assert final_state["next_run_at"] is None
    assert (
        final_state["interval_seconds"]
        == original_interval
    )

    assert final_payload["configured"] is False
    assert (
        final_payload["runtime_risk_payload"]
        is None
    )
    assert final_payload["analysis_payload"] is None

    print("Scheduler disabled: OK")
    print("Original interval restored: OK")
    print("Payload cleared: OK")

    print()
    print("=== v3.22 recurring verification passed ===")
    print("Slot 1 key:", slot_keys[0])
    print("Slot 2 key:", slot_keys[1])


if __name__ == "__main__":
    main()
