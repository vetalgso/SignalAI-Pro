from __future__ import annotations

from app.tradinggpt.engine.schemas import TradingGPTAnalyzeRequest
from app.tradinggpt.facade import TradingGPTFacade


def test_facade_exposes_analysis_engine(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    facade = TradingGPTFacade()

    result = facade.analyze(
        scoring_result=analyze_request.scoring.to_domain(),
        market_regime_result=(
            analyze_request.market_regime.to_domain()
        ),
        portfolio_result=(
            analyze_request.portfolio.to_domain()
        ),
    )

    payload = result.to_dict()

    assert payload["conviction"]["recommendation"] == "BUY"
    assert payload["conviction"]["score"] == 76.5
    assert payload["explanation"]["risk_level"] == "MEDIUM"
