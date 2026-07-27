from __future__ import annotations

from app.tradinggpt.engine import TradingGPTEngine

from verify_tradinggpt_pipeline import (
    build_market_regime_result,
    build_portfolio_result,
    build_scoring_result,
)


def main() -> None:
    result = TradingGPTEngine.analyze(
        scoring_result=build_scoring_result(),
        market_regime_result=build_market_regime_result(),
        portfolio_result=build_portfolio_result(),
    )

    assert result.conviction.level == "HIGH"
    assert result.conviction.recommendation == "BUY"
    assert result.conviction.score == 76.5

    payload = result.to_dict()

    assert "conviction" in payload
    assert "scoring" in payload
    assert "market_regime" in payload
    assert "portfolio" in payload

    print("TradingGPT Engine verification passed")


if __name__ == "__main__":
    main()
