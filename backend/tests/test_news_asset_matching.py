import asyncio
from html import escape

import httpx
import pytest

from app.news.assets import ASSETS, match_assets
from app.news.service import NewsService
from app.tradinggpt.quality_guard import AnalysisQualityGuard
from app.tradinggpt.signals.market_universe import FALLBACK_ASSETS


@pytest.mark.parametrize("text,symbol", [
    ("Bitcoin adoption", "BTC"), ("Ethereum upgrade", "ETH"),
    ("BNB Chain update", "BNB"), ("Solana validator update", "SOL"),
    ("XRP adoption", "XRP"), ("Cardano upgrade", "ADA"),
    ("Dogecoin activity", "DOGE"), ("TRON network update", "TRX"),
    ("Avalanche blockchain upgrade", "AVAX"), ("Chainlink integration", "LINK"),
    ("Sui network activity", "SUI"), ("The Open Network update", "TON"),
    ("Polkadot governance", "DOT"), ("Litecoin adoption", "LTC"),
    ("Bitcoin Cash upgrade", "BCH"), ("NEAR Protocol update", "NEAR"),
    ("Aptos upgrade", "APT"), ("Uniswap governance", "UNI"),
    ("Aave governance", "AAVE"), ("Cosmos Hub upgrade", "ATOM"),
    ("Zcash privacy", "ZEC"), ("Ethena update", "ENA"),
    ("Starknet upgrade", "STRK"), ("Arbitrum governance", "ARB"),
    ("Harmony blockchain", "ONE"), ("Succinct Network update", "PROVE"),
    ("Lorenzo Protocol governance", "BANK"), ("Bittensor subnet", "TAO"),
    ("Worldcoin update", "WLD"), ("Stellar Lumens", "XLM"),
    ("PAX Gold", "PAXG"), ("Fetch.ai", "FET"), ("Ondo Finance", "ONDO"),
    ("Saga protocol", "SAGA"), ("Official Trump memecoin", "TRUMP"),
    ("Pump.fun token", "PUMP"), ("Mubarak memecoin", "MUBARAK"),
    ("Circle Internet Group Tokenized bStocks", "CRCLB"),
])
def test_project_names_have_one_intended_asset(text, symbol):
    assert match_assets(text) == [symbol]


def test_all_scanner_fallback_assets_are_supported():
    assert set(FALLBACK_ASSETS) <= ASSETS.keys()


@pytest.mark.parametrize("text", [
    "President Trump signs a Bitcoin regulation bill",
    "Trump meets crypto executives and discusses token regulation",
    "An official Trump policy on digital assets",
    "#TRUMP discusses cryptocurrency policy",
    "Bitcoin is near a record; one bank will prove reserves",
    "A bank token platform is near token launch",
    "BANK provides LINK to ONE report; DOT is a punctuation mark",
    "A pump in prices started a saga about one atom",
    "Mubarak holiday greetings",
    "Circle reports USDC growth and CRCL shares gain",
    "Circle Internet Group shares rally",
    "The price of USDC is stable",
    "A stellar performance and a ripple effect",
    "An avalanche blocks a road",
    "Sui generis and an apt description",
])
def test_ambiguous_words_do_not_assign_tokens(text):
    assert not set(match_assets(text)) & {
        'TRUMP', 'NEAR', 'ONE', 'BANK', 'PROVE', 'LINK', 'DOT', 'PUMP', 'SAGA',
        'ATOM', 'MUBARAK', 'CRCLB', 'XLM', 'XRP', 'AVAX', 'SUI', 'APT',
    }


@pytest.mark.parametrize("symbol", ["NEAR", "ONE", "BANK", "TRUMP", "PUMP", "CRCLB", "LTC", "BCH"])
def test_explicit_tickers_and_pairs(symbol):
    for text in (f"${symbol} rises", f"{symbol}/USDT trading", f"{symbol}USDC market"):
        assert match_assets(text) == [symbol]
    assert symbol not in match_assets(f"${symbol}OTHER")
    assert symbol not in match_assets(f"MY{symbol}USDT")


@pytest.mark.parametrize("text,expected", [
    ("NEAR token gains", ["NEAR"]), ("token ONE trades", ["ONE"]),
    ("TRUMP token falls", ["TRUMP"]), ("$trump rises", ["TRUMP"]),
    ("Trump's memecoin rises", ["TRUMP"]), ("ltc rises", ["LTC"]),
    ("Bitcoin Cash and Ethereum Classic", ["BCH"]),
    ("Bitcoin SV, Bitcoin Gold and Bitcoin ABC", []),
    ("Bitcoin Cash versus Bitcoin", ["BTC", "BCH"]),
    ("BCH and BTC, BCH again", ["BTC", "BCH"]),
    ("TRUMPOTHER and bitcoinish", []),
    ("Litecoin &amp; Zcash", ["LTC", "ZEC"]),
    ("<b>NEAR</b>&nbsp;Protocol", ["NEAR"]),
    ('<a href="https://example.test/$TRUMP">Read more</a>', []),
    ('https://example.test/BCH?asset=NEARUSDT', []),
    ('<script>$TRUMP</script><style>.LTC {}</style>Bitcoin', ['BTC']),
])
def test_boundaries_entities_and_independent_mentions(text, expected):
    assert match_assets(text) == expected


def test_phrase_cannot_cross_title_and_description():
    assert match_assets("NEAR", "Protocol update") == []
    assert match_assets("Bitcoin", "Cash markets") == ["BTC"]


def test_rss_parser_filter_and_quality_use_the_same_matching_rules(monkeypatch):
    entries = [
        ("Litecoin adoption", "Litecoin and Zcash update"),
        ("Bitcoin Cash upgrade", "BCH developers release software"),
        ("Trump signs Bitcoin bill", "Political news, no meme token mention"),
        ("$TRUMP gains", "Official Trump memecoin activity"),
        ("NEAR Protocol update", "<b>NEAR</b>&nbsp;Protocol developers"),
        ("Circle shares gain", "Circle Internet Group and USDC"),
        ("CRCLB/USDT trading", "Circle tokenized bStocks"),
        ("Article", '<a href="https://example.test/$BANK">Read more</a>'),
    ]
    xml = '<rss><channel>' + ''.join(
        f'<item><title>{escape(t)}</title><description>{escape(d)}</description>'
        f'<link>https://example.test/{i}</link><pubDate>Tue, 22 Sep 2026 13:00:00 GMT</pubDate></item>'
        for i, (t, d) in enumerate(entries)
    ) + '</channel></rss>'
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url):
            return httpx.Response(200, text=xml, request=httpx.Request("GET", url))
    monkeypatch.setattr('app.news.service.httpx.AsyncClient', Client)
    service = NewsService()
    parsed = asyncio.run(service._fetch("Fixture", "https://example.test/rss"))
    assert [a['assets'] for a in parsed] == [
        ['LTC', 'ZEC'], ['BCH'], ['BTC'], ['TRUMP'], ['NEAR'], [], ['CRCLB'], [],
    ]
    assert all(a['status'] == 'unverified' for a in parsed)
    async def collected(): return parsed, []
    monkeypatch.setattr(service, '_all_articles', collected)
    for asset in ('LTC', 'BCH', 'TRUMP', 'NEAR', 'CRCLB'):
        result = asyncio.run(service.latest(asset=asset, limit=1))
        assert result['count'] == 1
        assert result['diagnostics']['coverage'] == 'SUPPORTED'
        assert result['diagnostics']['matcher_version'] == 1
        assert result['diagnostics']['sources_state'] == 'COMPLETE'
        quality = AnalysisQualityGuard.quality_breakdown(signal=None, forecast=None, news=result)
        assert quality.news.article_count == 1
        assert quality.news.points == 10  # No automatic verification or relaxed penalty.
        assert quality.news.diagnostics.matcher_version == 1
    empty = asyncio.run(service.latest(asset='DOT'))
    assert empty['count'] == 0 and empty['diagnostics']['coverage'] == 'SUPPORTED'
    unknown = asyncio.run(service.latest(asset='UNLISTED'))
    assert unknown['count'] == 0 and unknown['diagnostics']['coverage'] == 'UNSUPPORTED'
