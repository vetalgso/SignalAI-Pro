from __future__ import annotations

import re

from app.tradinggpt.schemas import AssistantIntent


INTENT_PATTERNS: list[tuple[AssistantIntent, tuple[str, ...]]] = [
    (
        "portfolio_allocation",
        (
            r"\bпортфел",
            r"\bраспредели",
            r"\bинвестирова",
            r"\bу меня\s+\d+",
            r"\ballocat",
        ),
    ),
    (
        "overnight_report",
        (
            r"за ночь",
            r"ночью",
            r"утренн",
            r"overnight",
            r"morning report",
        ),
    ),
    (
        "daily_opportunities",
        (
            r"какие сделки",
            r"что купить сегодня",
            r"лучшие сделки",
            r"возможности сегодня",
            r"trade ideas",
        ),
    ),
    (
        "risk_analysis",
        (
            r"\bриск",
            r"\bплеч",
            r"\bликвидац",
            r"\bstop loss",
            r"\bleverage",
        ),
    ),
    (
        "asset_analysis",
        (
            r"стоит ли покупать",
            r"стоит ли купить",
            r"проанализируй",
            r"анализ\s+\w+",
            r"should i buy",
        ),
    ),
    (
        "market_analysis",
        (
            r"что происходит на рынке",
            r"обзор рынка",
            r"рынок сегодня",
            r"market overview",
        ),
    ),
]


def classify_intent(message: str) -> AssistantIntent:
    normalized = message.lower().strip()

    for intent, patterns in INTENT_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return intent

    return "general"
