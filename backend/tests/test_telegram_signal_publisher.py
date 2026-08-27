import asyncio
import json
from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.tradinggpt.signals.telegram_publisher import (
    TelegramSignalDeliveryError,
    TelegramSignalPublisher,
    format_telegram_signal,
)


def _signal(**overrides: object) -> SimpleNamespace:
    values = {
        "id": 42,
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "side": "LONG",
        "confidence": Decimal("78.50"),
        "risk_level": "MEDIUM",
        "risk_reward": Decimal("1.25"),
        "entry_min": Decimal("78000"),
        "entry_max": Decimal("78100"),
        "stop_loss": Decimal("77400"),
        "take_profit_1": Decimal("78750"),
        "take_profit_2": Decimal("79400"),
        "take_profit_3": Decimal("80050"),
        "current_price": Decimal("77980.5"),
        "reasons": [
            (
                "Scanner and technical signal "
                "directions agree."
            ),
        ],
        "expires_at": datetime(
            2026,
            8,
            27,
            18,
            30,
            tzinfo=timezone.utc,
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_formatter_is_clear_and_complete() -> None:
    message = format_telegram_signal(
        _signal()
    )

    assert "НОВЫЙ ТОРГОВЫЙ СИГНАЛ" in message
    assert "BTC/USDT" in message
    assert "LONG — ПОКУПКА" in message
    assert "Вход: <b>78 000 — 78 100</b>" in message
    assert "Stop Loss: <b>77 400</b>" in message
    assert "Цель 1: <b>78 750</b>" in message
    assert "Цель 2: <b>79 400</b>" in message
    assert "Цель 3: <b>80 050</b>" in message
    assert "Уверенность: <b>78.5%</b>" in message
    assert "Риск: <b>СРЕДНИЙ</b>" in message
    assert "ID сигнала: #42" in message
    assert "Не финансовая рекомендация" in message
    assert "SignalAIE2E" not in message
    assert "GeneratorURL" not in message


def test_formatter_escapes_external_text() -> None:
    message = format_telegram_signal(
        _signal(
            reasons=[
                "<script>alert('x')</script>",
            ]
        )
    )

    assert "<script>" not in message
    assert "&lt;script&gt;" in message


def test_disabled_publisher_does_not_send() -> None:
    def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        raise AssertionError(
            "Disabled publisher made a request."
        )

    publisher = TelegramSignalPublisher(
        enabled=False,
        bot_token="unused",
        chat_id="unused",
        transport=httpx.MockTransport(
            handler
        ),
    )

    result = asyncio.run(
        publisher.publish(_signal())
    )

    assert result.delivered is False
    assert result.reason == "DISABLED"
    assert result.message_id is None


def test_publisher_sends_expected_payload() -> None:
    captured: dict[str, object] = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured["payload"] = json.loads(
            request.content.decode("utf-8")
        )

        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 321,
                },
            },
        )

    publisher = TelegramSignalPublisher(
        enabled=True,
        bot_token="test-token",
        chat_id="-100123",
        transport=httpx.MockTransport(
            handler
        ),
    )

    result = asyncio.run(
        publisher.publish(_signal())
    )

    assert result.delivered is True
    assert result.message_id == 321

    payload = captured["payload"]

    assert isinstance(payload, dict)
    assert payload["chat_id"] == "-100123"
    assert payload["parse_mode"] == "HTML"
    assert (
        payload["disable_web_page_preview"]
        is True
    )
    assert "BTC/USDT" in payload["text"]


def test_delivery_error_does_not_leak_token() -> None:
    def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            500,
            text="failure",
        )

    secret = "super-secret-token"

    publisher = TelegramSignalPublisher(
        enabled=True,
        bot_token=secret,
        chat_id="-100123",
        transport=httpx.MockTransport(
            handler
        ),
    )

    with pytest.raises(
        TelegramSignalDeliveryError
    ) as exc_info:
        asyncio.run(
            publisher.publish(_signal())
        )

    assert secret not in str(exc_info.value)
    assert "HTTP 500" in str(exc_info.value)
