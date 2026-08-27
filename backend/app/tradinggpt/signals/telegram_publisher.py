from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal
from html import escape

import httpx

from app.models.trading_signal import (
    TradingSignal,
)


class TelegramSignalConfigurationError(
    RuntimeError
):
    pass


class TelegramSignalDeliveryError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class TelegramPublishResult:
    delivered: bool
    reason: str
    message_id: int | None = None


def _decimal_text(
    value: Decimal | object,
) -> str:
    raw = format(
        Decimal(str(value)).normalize(),
        "f",
    )

    if "." in raw:
        raw = raw.rstrip("0").rstrip(".")

    whole, dot, fraction = raw.partition(".")

    sign = ""
    digits = whole

    if digits.startswith("-"):
        sign = "-"
        digits = digits[1:]

    grouped = ""

    while len(digits) > 3:
        grouped = (
            " "
            + digits[-3:]
            + grouped
        )
        digits = digits[:-3]

    grouped = sign + digits + grouped

    if dot:
        return f"{grouped}.{fraction}"

    return grouped


def _pair_label(symbol: str) -> str:
    normalized = symbol.strip().upper()

    for quote in (
        "FDUSD",
        "USDT",
        "USDC",
        "BUSD",
        "BTC",
        "ETH",
    ):
        if (
            normalized.endswith(quote)
            and len(normalized) > len(quote)
        ):
            return (
                f"{normalized[:-len(quote)]}"
                f"/{quote}"
            )

    return normalized


def _datetime_text(
    value: datetime | None,
) -> str:
    if value is None:
        return "не ограничен"

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return (
        value.astimezone(timezone.utc)
        .strftime("%d.%m.%Y %H:%M UTC")
    )


def _human_reason(value: str) -> str:
    normalized = value.strip()

    translations = {
        (
            "Scanner and technical signal "
            "directions agree."
        ): (
            "Рыночный сканер и технический "
            "анализ подтверждают одно "
            "направление."
        ),
    }

    return translations.get(
        normalized,
        normalized,
    )


def format_telegram_signal(
    signal: TradingSignal,
) -> str:
    side = signal.side.upper()

    if side == "LONG":
        direction = (
            "🟢 LONG — ПОКУПКА"
        )
    elif side == "SHORT":
        direction = (
            "🔴 SHORT — ПРОДАЖА"
        )
    else:
        direction = escape(side)

    risk_names = {
        "LOW": "НИЗКИЙ",
        "MEDIUM": "СРЕДНИЙ",
        "HIGH": "ВЫСОКИЙ",
    }

    entry_min = _decimal_text(
        signal.entry_min
    )
    entry_max = _decimal_text(
        signal.entry_max
    )

    entry = (
        entry_min
        if entry_min == entry_max
        else f"{entry_min} — {entry_max}"
    )

    lines = [
        "📈 <b>НОВЫЙ ТОРГОВЫЙ СИГНАЛ</b>",
        "",
        (
            f"<b>{escape(_pair_label(signal.symbol))}</b>"
            f" · {direction}"
        ),
        f"Таймфрейм: {escape(signal.timeframe)}",
        "",
        f"🎯 Вход: <b>{entry}</b>",
        (
            "🛑 Stop Loss: "
            f"<b>{_decimal_text(signal.stop_loss)}</b>"
        ),
        (
            "✅ Цель 1: "
            f"<b>{_decimal_text(signal.take_profit_1)}</b>"
        ),
    ]

    if signal.take_profit_2 is not None:
        lines.append(
            "✅ Цель 2: "
            f"<b>{_decimal_text(signal.take_profit_2)}</b>"
        )

    if signal.take_profit_3 is not None:
        lines.append(
            "✅ Цель 3: "
            f"<b>{_decimal_text(signal.take_profit_3)}</b>"
        )

    lines.extend(
        [
            "",
            (
                "Уверенность: "
                f"<b>{_decimal_text(signal.confidence)}%</b>"
            ),
            (
                "Риск: "
                f"<b>{risk_names.get(
                    signal.risk_level.upper(),
                    escape(signal.risk_level.upper()),
                )}</b>"
            ),
            (
                "Риск/прибыль до цели 1: "
                f"<b>1 : {_decimal_text(
                    signal.risk_reward
                )}</b>"
            ),
        ]
    )

    if signal.current_price is not None:
        lines.append(
            "Текущая цена: "
            f"{_decimal_text(signal.current_price)}"
        )

    lines.extend(
        [
            (
                "Сигнал актуален до: "
                f"{_datetime_text(signal.expires_at)}"
            ),
            f"ID сигнала: #{signal.id}",
        ]
    )

    reasons = [
        _human_reason(str(reason))
        for reason in signal.reasons[:3]
        if str(reason).strip()
    ]

    if reasons:
        lines.extend(
            [
                "",
                "<b>Почему сформирован:</b>",
            ]
        )

        lines.extend(
            f"• {escape(reason[:300])}"
            for reason in reasons
        )

    lines.extend(
        [
            "",
            (
                "⚠️ Не финансовая рекомендация. "
                "Соблюдайте риск-менеджмент."
            ),
        ]
    )

    return "\n".join(lines)


class TelegramSignalPublisher:
    def __init__(
        self,
        *,
        enabled: bool,
        bot_token: str,
        chat_id: str,
        timeout_seconds: float = 10.0,
        transport: (
            httpx.AsyncBaseTransport | None
        ) = None,
    ) -> None:
        self.enabled = enabled
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def publish(
        self,
        signal: TradingSignal,
    ) -> TelegramPublishResult:
        if not self.enabled:
            return TelegramPublishResult(
                delivered=False,
                reason="DISABLED",
            )

        if not self.bot_token:
            raise TelegramSignalConfigurationError(
                "Telegram signal bot token "
                "is not configured."
            )

        if not self.chat_id:
            raise TelegramSignalConfigurationError(
                "Telegram signal chat ID "
                "is not configured."
            )

        endpoint = (
            "https://api.telegram.org/bot"
            f"{self.bot_token}/sendMessage"
        )

        request_payload = {
            "chat_id": self.chat_id,
            "text": format_telegram_signal(
                signal
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    endpoint,
                    json=request_payload,
                )
        except httpx.HTTPError:
            raise TelegramSignalDeliveryError(
                "Telegram sendMessage "
                "request failed."
            ) from None

        if response.status_code >= 400:
            raise TelegramSignalDeliveryError(
                "Telegram sendMessage returned "
                f"HTTP {response.status_code}."
            )

        try:
            response_payload = response.json()
        except ValueError:
            raise TelegramSignalDeliveryError(
                "Telegram returned invalid JSON."
            ) from None

        if response_payload.get("ok") is not True:
            raise TelegramSignalDeliveryError(
                "Telegram rejected the message."
            )

        result = response_payload.get(
            "result",
            {},
        )
        message_id = result.get("message_id")

        if not isinstance(message_id, int):
            raise TelegramSignalDeliveryError(
                "Telegram response has no "
                "message ID."
            )

        return TelegramPublishResult(
            delivered=True,
            reason="DELIVERED",
            message_id=message_id,
        )
