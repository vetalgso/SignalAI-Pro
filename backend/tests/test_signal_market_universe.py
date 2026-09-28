from __future__ import annotations

import asyncio
from types import MethodType

from app.tradinggpt.modules.market_scanner import CryptoMarketScanner
from app.tradinggpt.signals.market_universe import (
    BinanceLiquidMarketUniverse,
    MarketUniverseSelection,
)


class FakeBinanceMarketService:
    async def trading_pairs(self) -> list[dict[str, str]]:
        return [
            {
                "symbol": "BTCUSDT",
                "base_asset": "BTC",
                "quote_asset": "USDT",
            },
            {
                "symbol": "ETHUSDT",
                "base_asset": "ETH",
                "quote_asset": "USDT",
            },
            {
                "symbol": "USDCUSDT",
                "base_asset": "USDC",
                "quote_asset": "USDT",
            },
            {
                "symbol": "BTCUPUSDT",
                "base_asset": "BTCUP",
                "quote_asset": "USDT",
            },
            {
                "symbol": "SOLEUR",
                "base_asset": "SOL",
                "quote_asset": "EUR",
            },
        ]

    async def ticker_24h(self) -> list[dict[str, str]]:
        return [
            {"symbol": "ETHUSDT", "quoteVolume": "200"},
            {"symbol": "BTCUSDT", "quoteVolume": "500"},
            {"symbol": "USDCUSDT", "quoteVolume": "900"},
            {"symbol": "BTCUPUSDT", "quoteVolume": "800"},
            {"symbol": "SOLEUR", "quoteVolume": "700"},
        ]


class FailingBinanceMarketService:
    async def trading_pairs(self) -> list[dict[str, str]]:
        raise RuntimeError("offline")

    async def ticker_24h(self) -> list[dict[str, str]]:
        raise AssertionError("must not be called")


class FakeUniverse:
    calls: list[int] = []

    async def select(self, *, limit: int) -> MarketUniverseSelection:
        self.calls.append(limit)
        return MarketUniverseSelection(
            assets=["BTC", "ETH", "SOL"],
            source="TEST_VOLUME",
        )


def test_selects_liquid_spot_usdt_assets() -> None:
    selection = asyncio.run(
        BinanceLiquidMarketUniverse(
            FakeBinanceMarketService()
        ).select(limit=10)
    )

    assert selection.source == "BINANCE_24H_QUOTE_VOLUME"
    assert selection.assets == ["BTC", "ETH"]
    assert selection.warnings == []


def test_excludes_fiat_pegged_assets() -> None:
    excluded = {
        "USDT",
        "USDC",
        "USDE",
        "USDS",
        "USD1",
        "RLUSD",
        "FDUSD",
        "TUSD",
        "USDP",
        "PYUSD",
        "BUSD",
        "GUSD",
        "DAI",
        "FRAX",
        "GHO",
        "MIM",
        "DOLA",
        "VAI",
        "UST",
        "USTC",
        "EUR",
        "AEUR",
        "EURC",
        "EURI",
        "BTCUP",
        "ETHDOWN",
    }

    for asset in excluded:
        assert not (
            BinanceLiquidMarketUniverse
            ._is_eligible_asset(asset)
        ), asset

    for asset in (
        "BTC",
        "ETH",
        "SOL",
        "PAXG",
        "XAUT",
    ):
        assert (
            BinanceLiquidMarketUniverse
            ._is_eligible_asset(asset)
        ), asset


def test_uses_bounded_fallback_on_provider_failure() -> None:
    selection = asyncio.run(
        BinanceLiquidMarketUniverse(
            FailingBinanceMarketService()
        ).select(limit=3)
    )

    assert selection.source == "STATIC_FALLBACK"
    assert selection.assets == ["BTC", "ETH", "BNB"]
    assert selection.warnings == [
        "DYNAMIC_UNIVERSE_FAILED:RuntimeError"
    ]


def test_scanner_uses_dynamic_universe() -> None:
    universe = FakeUniverse()
    universe.calls = []
    scanner = CryptoMarketScanner(
        crypto_asset_module=object(),
        universe_provider=universe,
    )

    async def analyze_none(
        self: CryptoMarketScanner,
        asset: str,
        risk_level: str,
    ) -> None:
        assert risk_level == "medium"
        assert asset in {"BTC", "ETH", "SOL"}
        return None

    scanner._analyze_asset = MethodType(analyze_none, scanner)

    result = asyncio.run(scanner.scan(limit=3))

    assert universe.calls == [3]
    assert result["universe_source"] == "TEST_VOLUME"
    assert result["universe_assets"] == ["BTC", "ETH", "SOL"]
    assert result["scanned_assets"] == 3


def test_excludes_one_letter_u_pegged_asset() -> None:
    assert (
        BinanceLiquidMarketUniverse
        ._is_eligible_asset("U")
        is False
    )


def test_u_pegged_asset_does_not_take_ranked_slot() -> None:
    assets = BinanceLiquidMarketUniverse._rank_assets(
        pairs=[
            {
                "symbol": "UUSDT",
                "base_asset": "U",
                "quote_asset": "USDT",
            },
            {
                "symbol": "BTCUSDT",
                "base_asset": "BTC",
                "quote_asset": "USDT",
            },
        ],
        tickers=[
            {
                "symbol": "UUSDT",
                "quoteVolume": "999999999",
            },
            {
                "symbol": "BTCUSDT",
                "quoteVolume": "1000000",
            },
        ],
        limit=1,
    )

    assert assets == ["BTC"]
