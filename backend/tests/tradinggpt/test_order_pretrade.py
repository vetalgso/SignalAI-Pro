from __future__ import annotations

from app.tradinggpt.orders import BinanceOrderAdapter, OrderIntent


class FakeClient:
    def get_symbol_info(self, symbol: str):
        return {
            "symbol": symbol, "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT",
            "filters": [
                {"filterType":"PRICE_FILTER", "minPrice":"0.01", "maxPrice":"1000000", "tickSize":"0.10"},
                {"filterType":"LOT_SIZE", "minQty":"0.0001", "maxQty":"100", "stepSize":"0.0001"},
                {"filterType":"MIN_NOTIONAL", "minNotional":"5"},
            ],
        }
    def get_symbol_ticker(self, **params): return {"price":"62000.12"}
    def get_asset_balance(self, **params): return {"free":"1000"}


def make_intent(**overrides):
    data = dict(exchange="BINANCE", market_type="SPOT", symbol="BTCUSDT", side="BUY", order_type="LIMIT", quantity=0.00019, reference_price=62000.17, stop_loss=None, take_profit_1=None, take_profit_2=None, leverage=1, reduce_only=False)
    data.update(overrides)
    return OrderIntent(**data)


def test_preview_normalizes_price_and_quantity():
    preview = BinanceOrderAdapter(client=FakeClient()).preview(intent=make_intent())
    assert preview.valid is True
    assert preview.normalized_quantity == 0.0001
    assert preview.normalized_price == 62000.1


def test_preview_rejects_below_min_notional():
    preview = BinanceOrderAdapter(client=FakeClient()).preview(intent=make_intent(quantity=0.0001, reference_price=1000.0))
    assert preview.valid is False
    assert any("below minimum" in error for error in preview.errors)


def test_preview_rejects_insufficient_balance():
    class PoorClient(FakeClient):
        def get_asset_balance(self, **params): return {"free":"1"}
    preview = BinanceOrderAdapter(client=PoorClient()).preview(intent=make_intent())
    assert preview.valid is False
    assert any("Insufficient USDT" in error for error in preview.errors)
