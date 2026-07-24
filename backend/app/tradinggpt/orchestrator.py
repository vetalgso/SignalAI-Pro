from __future__ import annotations

import re
from typing import Any

from app.tradinggpt.intent_classifier import classify_intent
from app.tradinggpt.schemas import (
    AnalysisFactor,
    AssistantChatRequest,
    AssistantChatResponse,
    PortfolioAllocationItem,
)


DISCLAIMER = (
    "Информация носит аналитический характер и не является индивидуальной "
    "инвестиционной рекомендацией или гарантией результата."
)


class TradingGPTOrchestrator:
    async def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        intent = classify_intent(request.message)

        if intent == "portfolio_allocation":
            return self._build_portfolio_response(request)

        if intent == "asset_analysis":
            return self._build_asset_response(request)

        if intent == "daily_opportunities":
            return self._build_daily_opportunities_response(request)

        if intent == "overnight_report":
            return self._build_overnight_response(request)

        if intent == "risk_analysis":
            return self._build_risk_response(request)

        if intent == "market_analysis":
            return self._build_market_response(request)

        return self._build_general_response(request)

    def _build_portfolio_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        context = request.context
        capital = context.capital

        allocations = self._allocation_for_risk(context.risk_level)
        portfolio = [
            PortfolioAllocationItem(
                asset=asset,
                allocation_percent=percent,
                amount=round(capital * percent / 100, 2) if capital else None,
                reason=reason,
            )
            for asset, percent, reason in allocations
        ]

        capital_text = (
            f"Для капитала {capital:,.2f} {context.currency}"
            if capital
            else "Для указанного риск-профиля"
        )

        answer = (
            f"{capital_text} я предлагаю диверсифицированную базовую структуру. "
            f"Профиль риска: {context.risk_level}. "
            "Портфель сочетает активы роста, защитные инструменты и резерв "
            "ликвидности. Перед реальным инвестированием необходимо уточнить "
            "срок, текущие активы и допустимую просадку."
        )

        return AssistantChatResponse(
            intent="portfolio_allocation",
            answer=answer,
            confidence=68,
            risk=context.risk_level,
            market_view="mixed",
            factors=[
                AnalysisFactor(
                    type="diversification",
                    score=82,
                    summary="Капитал распределён между несколькими классами активов.",
                ),
                AnalysisFactor(
                    type="liquidity",
                    score=75,
                    summary="Часть капитала оставлена в денежном резерве.",
                ),
                AnalysisFactor(
                    type="personalization",
                    score=55,
                    summary="Распределение основано пока только на базовом риск-профиле.",
                ),
            ],
            portfolio=portfolio,
            follow_up_questions=[
                "На какой срок вы планируете инвестировать?",
                "Какая максимальная просадка для вас приемлема?",
                "Какие активы уже находятся в вашем портфеле?",
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_asset_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        asset = self._extract_asset(request.message)

        answer = (
            f"Для полноценного анализа {asset} системе нужно объединить текущую "
            "цену, технические индикаторы, прогнозы, новости, макроэкономику и "
            "ваш риск-профиль. Сейчас TradingGPT распознал запрос, но ещё не "
            "подключён к универсальному источнику данных для всех классов активов."
        )

        return AssistantChatResponse(
            intent="asset_analysis",
            answer=answer,
            confidence=40,
            risk=request.context.risk_level,
            market_view="neutral",
            factors=[
                AnalysisFactor(
                    type="technical",
                    score=0,
                    summary="Рыночные данные пока не были запрошены.",
                ),
                AnalysisFactor(
                    type="news",
                    score=0,
                    summary="Новостной модуль ещё не подключён к ответу ассистента.",
                ),
                AnalysisFactor(
                    type="risk",
                    score=60,
                    summary=f"Использован профиль риска: {request.context.risk_level}.",
                ),
            ],
            follow_up_questions=[
                f"Какой горизонт покупки {asset}: день, месяц или год?",
                "Какую долю капитала вы готовы вложить?",
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_daily_opportunities_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="daily_opportunities",
            answer=(
                "Сканер ежедневных возможностей пока не подключён. На следующем "
                "этапе он будет сравнивать активы по силе сигнала, прогнозу, "
                "волатильности, новостям и соотношению риск/доходность."
            ),
            confidence=25,
            risk=request.context.risk_level,
            market_view="mixed",
            factors=[
                AnalysisFactor(
                    type="signal_scanner",
                    score=0,
                    summary="Мультиактивный сканер ещё не реализован.",
                ),
                AnalysisFactor(
                    type="risk_filter",
                    score=65,
                    summary="Будущие идеи будут фильтроваться по риск-профилю.",
                ),
            ],
            follow_up_questions=[
                "Какие рынки сканировать: криптовалюты, акции, Forex или металлы?",
                "Допускаете ли вы краткосрочные сделки?",
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_overnight_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="overnight_report",
            answer=(
                "Модуль утреннего отчёта подготовлен на уровне API, но пока не "
                "подключён к историческим ценам, новостям и экономическому "
                "календарю. После подключения он будет показывать изменения цен, "
                "ключевые события и влияние на выбранные активы."
            ),
            confidence=25,
            risk=request.context.risk_level,
            market_view="neutral",
            factors=[
                AnalysisFactor(
                    type="market_changes",
                    score=0,
                    summary="Данные за ночь пока не загружены.",
                ),
                AnalysisFactor(
                    type="news",
                    score=0,
                    summary="Новостные события ещё не агрегированы в отчёт.",
                ),
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_risk_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        leverage = self._extract_leverage(request.message)
        risk_score = min(100, 35 + leverage * 4) if leverage else 55

        if leverage and leverage >= 10:
            answer = (
                f"Плечо x{leverage} создаёт высокий риск быстрой ликвидации. "
                "До расчёта конкретного стоп-лосса и размера позиции такую сделку "
                "не следует считать приемлемой."
            )
            risk = "high"
        else:
            answer = (
                "Для оценки риска нужны размер позиции, цена входа, стоп-лосс, "
                "размер капитала и используемое плечо."
            )
            risk = request.context.risk_level

        return AssistantChatResponse(
            intent="risk_analysis",
            answer=answer,
            confidence=70 if leverage else 45,
            risk=risk,
            market_view="neutral",
            factors=[
                AnalysisFactor(
                    type="leverage",
                    score=risk_score,
                    summary=(
                        f"Обнаружено плечо x{leverage}."
                        if leverage
                        else "Плечо в сообщении не обнаружено."
                    ),
                ),
                AnalysisFactor(
                    type="position_size",
                    score=0,
                    summary="Размер позиции пока не рассчитан.",
                ),
            ],
            follow_up_questions=[
                "Каков размер вашего капитала?",
                "Какая цена входа и стоп-лосс?",
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_market_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="market_analysis",
            answer=(
                "Общий рыночный обзор будет формироваться из данных Crypto, "
                "Stocks, Forex, Metals, Indices и Macro. Сейчас доступна только "
                "часть криптовалютной инфраструктуры, поэтому достоверный общий "
                "вывод пока не формируется."
            ),
            confidence=30,
            risk=request.context.risk_level,
            market_view="mixed",
            factors=[
                AnalysisFactor(
                    type="crypto",
                    score=65,
                    summary="Криптовалютный модуль уже существует в проекте.",
                ),
                AnalysisFactor(
                    type="traditional_markets",
                    score=0,
                    summary="Акции, Forex, металлы и индексы ещё не подключены.",
                ),
            ],
            disclaimer=DISCLAIMER,
        )

    def _build_general_response(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="general",
            answer=(
                "Я могу помочь с анализом активов, распределением капитала, "
                "рисками, рыночными возможностями и утренними отчётами. "
                "Сформулируйте вопрос, например: «Как распределить 5000 долларов?» "
                "или «Стоит ли покупать BTC?»."
            ),
            confidence=75,
            risk=request.context.risk_level,
            market_view="neutral",
            disclaimer=DISCLAIMER,
        )

    @staticmethod
    def _extract_asset(message: str) -> str:
        known_assets = (
            "BTC",
            "ETH",
            "SOL",
            "XRP",
            "TSLA",
            "AAPL",
            "NVDA",
            "GOLD",
            "XAU",
            "SILVER",
            "XAG",
            "NASDAQ",
            "SP500",
            "EURUSD",
        )

        upper_message = message.upper()

        for asset in known_assets:
            if asset in upper_message:
                return asset

        return "выбранного актива"

    @staticmethod
    def _extract_leverage(message: str) -> int | None:
        match = re.search(r"(?:x|х)\s*(\d+)|(\d+)\s*(?:x|х)", message.lower())
        if not match:
            return None

        raw = match.group(1) or match.group(2)
        return int(raw)

    @staticmethod
    def _allocation_for_risk(
        risk_level: str,
    ) -> list[tuple[str, float, str]]:
        allocations: dict[str, list[tuple[str, float, str]]] = {
            "low": [
                ("Cash / USD", 30, "Резерв ликвидности и снижение волатильности."),
                ("Gold", 25, "Защитная часть портфеля."),
                ("NASDAQ ETF", 20, "Долгосрочная доля акций роста."),
                ("BTC", 15, "Ограниченная доля высокорискового актива."),
                ("ETH", 10, "Дополнительная диверсификация криптовалютной части."),
            ],
            "medium": [
                ("BTC", 25, "Основная криптовалютная позиция."),
                ("ETH", 20, "Диверсификация криптовалютной части."),
                ("NASDAQ ETF", 20, "Экспозиция к технологическому сектору."),
                ("Gold", 15, "Снижение общей волатильности."),
                ("S&P 500 ETF", 10, "Широкая диверсификация по акциям."),
                ("Cash / USD", 10, "Резерв для новых возможностей."),
            ],
            "high": [
                ("BTC", 35, "Высокая потенциальная доходность при высоком риске."),
                ("ETH", 25, "Крупный криптовалютный актив роста."),
                ("NASDAQ ETF", 20, "Акции технологического сектора."),
                ("Growth Stocks", 10, "Дополнительная доля активов роста."),
                ("Gold", 5, "Небольшая защитная позиция."),
                ("Cash / USD", 5, "Минимальный резерв ликвидности."),
            ],
        }

        return allocations.get(risk_level, allocations["medium"])
