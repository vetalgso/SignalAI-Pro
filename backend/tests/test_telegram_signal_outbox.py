from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import Index, UniqueConstraint

from app.models.trading_signal import (
    TelegramSignalDelivery,
)
from app.tradinggpt.signals.schemas import (
    SignalCreateRequest,
    SignalStatus,
    SignalTransitionRequest,
)
from app.tradinggpt.signals.service import (
    DuplicateSignalError,
    TradingSignalService,
)


class FakeDatabase:
    def __init__(
        self,
        operations: list[str],
    ) -> None:
        self.operations = operations

    def commit(self) -> None:
        self.operations.append("commit")

    def refresh(self, _: object) -> None:
        self.operations.append("refresh")


class FakeRepository:
    def __init__(
        self,
        existing: object | None = None,
    ) -> None:
        self.operations: list[str] = []
        self.db = FakeDatabase(
            self.operations
        )
        self.existing = existing
        self.signal: object | None = None
        self.next_event_id = 501
        self.delivery_requests: list[
            dict[str, object]
        ] = []

    def get(
        self,
        _: int,
    ) -> object | None:
        return self.signal

    def get_by_fingerprint(
        self,
        _: str,
    ) -> object | None:
        return self.existing

    def add(self, signal: object) -> object:
        signal.id = 101
        self.operations.append("signal")
        return signal

    def add_event(
        self,
        **_: object,
    ) -> object:
        event = SimpleNamespace(
            id=self.next_event_id
        )
        self.next_event_id += 1
        self.operations.append("event")
        return event

    def enqueue_telegram_delivery(
        self,
        signal_id: int,
        *,
        delivery_type: str,
        event_id: int | None,
    ) -> object:
        self.delivery_requests.append({
            "signal_id": signal_id,
            "delivery_type": delivery_type,
            "event_id": event_id,
        })
        self.operations.append("delivery")
        return object()


def _request() -> SignalCreateRequest:
    generated_at = datetime(
        2026,
        8,
        27,
        10,
        0,
        tzinfo=timezone.utc,
    )

    return SignalCreateRequest(
        exchange="BINANCE",
        market_type="SPOT",
        symbol="BTCUSDT",
        timeframe="1H",
        side="LONG",
        strategy="TECHNICAL_CONFLUENCE_V1",
        confidence=Decimal("78.50"),
        risk_level="MEDIUM",
        entry_min=Decimal("78000"),
        entry_max=Decimal("78100"),
        stop_loss=Decimal("77400"),
        take_profit_1=Decimal("78750"),
        take_profit_2=Decimal("79400"),
        take_profit_3=Decimal("80050"),
        current_price=Decimal("77980"),
        reasons=[
            (
                "Scanner and technical signal "
                "directions agree."
            ),
        ],
        source="MARKET_SCANNER",
        generated_at=generated_at,
        expires_at=(
            generated_at
            + timedelta(hours=6)
        ),
    )


def test_signal_and_delivery_share_commit() -> None:
    repository = FakeRepository()

    signal = TradingSignalService(
        repository
    ).create(_request())

    assert signal.id == 101
    assert repository.delivery_requests == [{
        "signal_id": 101,
        "delivery_type": "SIGNAL_CREATED",
        "event_id": 501,
    }]
    assert repository.operations == [
        "signal",
        "event",
        "delivery",
        "commit",
        "refresh",
    ]


def test_duplicate_does_not_enqueue_delivery() -> None:
    repository = FakeRepository(
        existing=SimpleNamespace(id=77)
    )

    with pytest.raises(
        DuplicateSignalError
    ):
        TradingSignalService(
            repository
        ).create(_request())

    assert repository.delivery_requests == []
    assert repository.operations == []


def test_transition_and_delivery_share_commit() -> None:
    repository = FakeRepository()
    repository.signal = SimpleNamespace(
        id=101,
        status=SignalStatus.ACTIVE.value,
        current_price=Decimal("77980"),
        updated_at=None,
        entry_reached_at=None,
        closed_at=None,
    )

    signal = TradingSignalService(
        repository
    ).transition(
        signal_id=101,
        request=SignalTransitionRequest(
            status=(
                SignalStatus.ENTRY_REACHED
            ),
            price=Decimal("78050"),
            note="Entry range reached.",
        ),
        event_type=(
            "MARKET_STATUS_CHANGED"
        ),
        event_payload={
            "automatic": True,
        },
    )

    assert (
        signal.status
        == SignalStatus.ENTRY_REACHED.value
    )
    assert signal.entry_reached_at is not None
    assert repository.delivery_requests == [{
        "signal_id": 101,
        "delivery_type": (
            "SIGNAL_STATUS_CHANGED"
        ),
        "event_id": 501,
    }]
    assert repository.operations == [
        "event",
        "delivery",
        "commit",
        "refresh",
    ]


def test_delivery_model_has_unique_event() -> None:
    table = TelegramSignalDelivery.__table__

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    }

    assert (
        "uq_telegram_signal_deliveries_event_id"
        in unique_names
    )
    assert (
        "uq_telegram_signal_deliveries_signal_id"
        not in unique_names
    )

    index_names = {
        index.name
        for index in table.indexes
        if isinstance(index, Index)
    }

    assert (
        "ix_telegram_signal_deliveries_"
        "status_next_attempt"
        in index_names
    )

    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key
        in table.c.signal_id.foreign_keys
    }

    assert foreign_keys == {
        "trading_signals.id"
    }

    event_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key
        in table.c.event_id.foreign_keys
    }

    assert event_foreign_keys == {
        "trading_signal_events.id"
    }
    assert table.c.event_id.nullable is True
    assert (
        table.c.delivery_type.default.arg
        == "SIGNAL_CREATED"
    )

    assert table.c.status.default.arg == "PENDING"
    assert table.c.attempt_count.default.arg == 0


def test_migration_contract() -> None:
    from pathlib import Path

    migration = Path(
        "alembic/versions/"
        "20260827_0017_add_telegram_signal_outbox.py"
    ).read_text(encoding="utf-8")

    for value in (
        'revision = "20260827_0017"',
        'down_revision = "20260825_0016"',
        '"telegram_signal_deliveries"',
        (
            '"uq_telegram_signal_"'
            '\n                '
            '"deliveries_signal_id"'
        ),
        '"telegram_message_id"',
    ):
        assert value in migration




def test_lifecycle_migration_contract() -> None:
    import ast
    from pathlib import Path

    migration = Path(
        "alembic/versions/"
        "20260828_0018_add_telegram_signal_event_deliveries.py"
    ).read_text(encoding="utf-8")

    tree = ast.parse(migration)

    string_constants = {
        node.value
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        )
    }

    required = {
        "20260828_0018",
        "20260827_0017",
        "telegram_signal_deliveries",
        "delivery_type",
        "event_id",
        "SIGNAL_CREATED",
        (
            "uq_telegram_signal_"
            "deliveries_event_id"
        ),
        (
            "fk_telegram_signal_"
            "deliveries_event_id"
        ),
        (
            "uq_telegram_signal_"
            "deliveries_signal_id"
        ),
    }

    missing = required - string_constants

    assert not missing, sorted(missing)

    assert "def upgrade()" in migration
    assert "def downgrade()" in migration
