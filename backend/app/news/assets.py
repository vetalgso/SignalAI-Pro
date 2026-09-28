"""Curated news mentions, not an automatic mapping of every exchange ticker.

Common words/person names require explicit token notation or a project phrase.
Unknown assets remain unsupported. Keep aliases reviewable and deterministic.
"""
from html.parser import HTMLParser
import re
import unicodedata


MATCHER_VERSION = 1
# Public compatibility export: callers use ASSETS to inspect dictionary coverage.
ASSETS: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin",), "ETH": ("ethereum", "ether"),
    "BNB": ("binance coin", "bnb chain"), "SOL": ("solana",),
    "XRP": ("ripple labs",), "ADA": ("cardano",),
    "DOGE": ("dogecoin",), "TRX": ("tron network", "tron blockchain"),
    "AVAX": ("avalanche network", "avalanche blockchain"), "LINK": ("chainlink",),
    "SUI": ("sui network", "sui blockchain"), "TON": ("toncoin", "the open network"),
    "DOT": ("polkadot",), "LTC": ("litecoin",), "BCH": ("bitcoin cash",),
    "NEAR": ("near protocol",), "APT": ("aptos",), "UNI": ("uniswap",),
    "AAVE": ("aave",), "ATOM": ("cosmos hub",),
    "ZEC": ("zcash",), "ENA": ("ethena",), "STRK": ("starknet",),
    "ARB": ("arbitrum",), "ONE": ("harmony protocol", "harmony blockchain"),
    "PROVE": ("succinct network", "succinct protocol"), "BANK": ("lorenzo protocol",),
    "TAO": ("bittensor",), "WLD": ("worldcoin", "world network"),
    "XLM": ("stellar network", "stellar blockchain", "stellar lumens"),
    "PAXG": ("pax gold",), "FET": ("fetch.ai",), "ONDO": ("ondo finance",),
    "SAGA": ("saga protocol", "saga blockchain"),
    "TRUMP": (), "PUMP": (), "MUBARAK": (),
    "CRCLB": ("circle internet group tokenized bstocks", "circle tokenized bstocks"),
}

# A bare uppercase spelling is still ambiguous for these words/names.
_GUARDED = {"SOL", "ADA", "LINK", "SUI", "TON", "DOT", "NEAR", "APT", "ATOM",
            "ONE", "PROVE", "BANK", "SAGA", "TRUMP", "PUMP", "MUBARAK"}


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(value: str) -> str:
    parser = _VisibleText()
    parser.feed(value)
    parser.close()
    text = unicodedata.normalize("NFKC", "".join(parser.parts))
    text = text.translate(str.maketrans({"’": "'", "–": "-", "—": "-", "‑": "-"}))
    # A URL/HTML attribute is not a textual mention of its path or query tickers.
    text = re.sub(r"(?:https?://|www\.)\S+", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _name_pattern(name: str) -> str:
    pattern = re.escape(name).replace(r"\ ", r"\s+")
    if name == "bitcoin":
        pattern += r"(?![\s-]+(?:cash|sv|gold|abc)\b)"
    elif name in {"ethereum", "ether"}:
        pattern += r"(?![\s-]+classic\b)"
    return rf"(?<!\w){pattern}(?!\w)"


_NAMES = {symbol: tuple(re.compile(_name_pattern(name), re.IGNORECASE) for name in names)
          for symbol, names in ASSETS.items()}
_EXPLICIT = {symbol: re.compile(
    rf"(?<!\w)(?:\${symbol}|{symbol}[/_-]?(?:USDT|USDC))(?!\w)", re.IGNORECASE)
    for symbol in ASSETS}
_BARE = {symbol: re.compile(rf"(?<!\w){symbol}(?!\w)", re.IGNORECASE)
         for symbol in ASSETS if symbol not in _GUARDED}
# Uppercase ticker required: ordinary phrases such as 'one token' and 'near token'
# must not be treated as Harmony/NEAR mentions merely because this is a crypto feed.
_CONTEXT = {symbol: re.compile(
    rf"(?<!\w)(?:{symbol}\s+(?i:token|memecoin|meme coin)s?\b|"
    rf"(?i:token|memecoin|meme coin)\s+{symbol}(?!\w))")
    for symbol in _GUARDED - {"BANK"}}
_SPECIAL = {
    "TRUMP": re.compile(r"(?<!\w)(?:official\s+trump\s+(?:token|memecoin|meme coin)|"
                        r"trump(?:'s)?\s+(?:memecoin|meme coin))(?!\w)", re.IGNORECASE),
    "PUMP": re.compile(r"(?<!\w)pump\.fun(?:'s)?\s+token\b", re.IGNORECASE),
    "MUBARAK": re.compile(r"(?<!\w)mubarak\s+(?:token|memecoin|meme coin)\b", re.IGNORECASE),
}


def match_assets(title: str, description: str = "") -> list[str]:
    # Do not join fields: title 'NEAR' + description 'Protocol ...' is not a phrase.
    fields = (visible_text(title), visible_text(description))
    found = []
    for symbol in ASSETS:
        patterns = (*_NAMES[symbol], _EXPLICIT[symbol],
                    *([_BARE[symbol]] if symbol in _BARE else []),
                    *([_CONTEXT[symbol]] if symbol in _CONTEXT else []),
                    *([_SPECIAL[symbol]] if symbol in _SPECIAL else []))
        if any(pattern.search(field) for field in fields for pattern in patterns):
            found.append(symbol)
    return found
