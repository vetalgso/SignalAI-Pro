from __future__ import annotations

import re
from typing import Any

from app.tradinggpt.intent_classifier import classify_intent
from app.tradinggpt.modules.crypto_asset import CryptoAssetAnalysisModule, SUPPORTED_CRYPTO_ASSETS
from app.tradinggpt.portfolio import PortfolioEngine
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
            asset = self._extract_asset(request.message)

            if asset in SUPPORTED_CRYPTO_ASSETS:
                return await CryptoAssetAnalysisModule().analyze(asset, request)

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

        current_allocations = (
            dict(context.current_allocations)
            if context.current_allocations
            else {
                asset: 0.0
                for asset in context.existing_assets
            }
        )

        engine_result = PortfolioEngine.build(
            risk_level=context.risk_level,
            capital=capital,
            currency=context.currency,
            max_position_percent=(
                context.max_position_percent
            ),
            current_allocations=current_allocations,
            min_trade_amount=context.min_trade_amount,
            trading_fee_percent=(
                context.trading_fee_percent
            ),
            rebalance_tolerance_percent=(
                context.rebalance_tolerance_percent
            ),
            trade_rounding_amount=(
                context.trade_rounding_amount
            ),
        )

        portfolio = [
            PortfolioAllocationItem(
                asset=position.asset,
                allocation_percent=round(
                    position.target_percent,
                    2,
                ),
                amount=position.amount,
                reason=(
                    f"[{position.action}] "
                    f"{position.reason}"
                ),
            )
            for position in engine_result.positions
        ]

        capital_text = (
            f"Для капитала {capital:,.2f} "
            f"{context.currency.upper()}"
            if capital
            else "Для указанного риск-профиля"
        )

        warning_text = (
            " Предупреждения: "
            + " ".join(engine_result.warnings)
            if engine_result.warnings
            else ""
        )

        active_trades = [
            trade
            for trade in engine_result.trades
            if trade.action != "HOLD"
        ]

        trade_summary = (
            f" Для ребалансировки требуется "
            f"{len(active_trades)} операций."
            if current_allocations
            else ""
        )

        answer = (
            f"{capital_text} сформирована целевая структура портфеля. "
            f"Профиль риска: {context.risk_level}. "
            f"Риск портфеля: "
            f"{engine_result.portfolio_risk_score:.1f}/100. "
            f"Максимальный риск на одну сделку: "
            f"{engine_result.max_risk_per_trade_percent:.2f}% "
            f"капитала. "
            f"Инвестировано: "
            f"{engine_result.invested_percent:.1f}%. "
            f"Денежный резерв: "
            f"{engine_result.cash_reserve_percent:.1f}%. "
            f"Максимальная доля одной позиции: "
            f"{engine_result.max_position_percent:.1f}%."
            f"{trade_summary}"
            f"{warning_text}"
        )

        liquidity_score = round(
            min(
                100.0,
                engine_result.cash_reserve_percent * 4,
            )
        )

        personalization_score = 75

        if context.current_allocations:
            personalization_score += 15
        elif context.existing_assets:
            personalization_score += 10

        if capital:
            personalization_score += 5

        return AssistantChatResponse(
            intent="portfolio_allocation",
            answer=answer,
            confidence=82,
            risk=context.risk_level,
            market_view="mixed",
            factors=[
                AnalysisFactor(
                    type="portfolio_risk",
                    score=round(
                        engine_result.portfolio_risk_score
                    ),
                    summary=(
                        "Расчётный уровень риска портфеля: "
                        f"{engine_result.portfolio_risk_score:.1f}"
                        "/100."
                    ),
                ),
                AnalysisFactor(
                    type="liquidity",
                    score=liquidity_score,
                    summary=(
                        "Денежный резерв составляет "
                        f"{engine_result.cash_reserve_percent:.1f}%."
                    ),
                ),
                AnalysisFactor(
                    type="position_limit",
                    score=100,
                    summary=(
                        "Максимальная доля одной позиции ограничена "
                        f"уровнем "
                        f"{engine_result.max_position_percent:.1f}%."
                    ),
                ),
                AnalysisFactor(
                    type="personalization",
                    score=min(
                        personalization_score,
                        100,
                    ),
                    summary=(
                        "Распределение учитывает капитал, "
                        "риск-профиль, лимит позиции и "
                        "текущие доли активов."
                    ),
                ),
            ],
            portfolio=portfolio,
            follow_up_questions=[
                (
                    "Подтвердите, готовы ли вы выполнить "
                    "предложенную ребалансировку."
                ),
                (
                    "Какая максимальная просадка портфеля для вас "
                    "приемлема?"
                ),
            ],
            details={
                "portfolio_risk_score": (
                    engine_result.portfolio_risk_score
                ),
                "cash_reserve_percent": (
                    engine_result.cash_reserve_percent
                ),
                "invested_percent": (
                    engine_result.invested_percent
                ),
                "max_position_percent": (
                    engine_result.max_position_percent
                ),
                "max_risk_per_trade_percent": (
                    engine_result.max_risk_per_trade_percent
                ),
                "warnings": engine_result.warnings,
                "execution": {
                    "min_trade_amount": (
                        engine_result.min_trade_amount
                    ),
                    "trading_fee_percent": (
                        engine_result.trading_fee_percent
                    ),
                    "rebalance_tolerance_percent": (
                        engine_result
                        .rebalance_tolerance_percent
                    ),
                    "trade_rounding_amount": (
                        engine_result.trade_rounding_amount
                    ),
                    "estimated_total_fees": (
                        engine_result.estimated_total_fees
                    ),
                },
                "trade_plan": [
                    {
                        "asset": trade.asset,
                        "action": trade.action,
                        "current_percent": round(
                            trade.current_percent,
                            2,
                        ),
                        "target_percent": round(
                            trade.target_percent,
                            2,
                        ),
                        "delta_percent": round(
                            trade.delta_percent,
                            2,
                        ),
                        "current_amount": (
                            trade.current_amount
                        ),
                        "target_amount": (
                            trade.target_amount
                        ),
                        "trade_amount": (
                            trade.trade_amount
                        ),
                        "estimated_fee": (
                            trade.estimated_fee
                        ),
                        "net_cash_flow": (
                            trade.net_cash_flow
                        ),
                        "currency": trade.currency,
                        "reason": trade.reason,
                    }
                    for trade in engine_result.trades
                ],
                "portfolio": engine_result.to_dict(),
            },
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
