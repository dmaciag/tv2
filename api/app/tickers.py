CRYPTO_SHORTHANDS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "FTM": "WFTM-USD",
    "FTM-USD": "WFTM-USD",
}


def resolve_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    return CRYPTO_SHORTHANDS.get(ticker, ticker)
