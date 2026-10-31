import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "crypto.db"
DAY_MS = 86_400_000
REQUEST_PAUSE_S = 1.0

COINS = {
    "ETH-USD": ("ETH_BTC", "tETHUSD"),
    "XRP-USD": ("XRP_BTC", "tXRPUSD"),
    "DOGE-USD": ("DOGE_BTC", "tDOGE:USD"),
    "FTM-USD": (None, "tFTMUSD"),
}

session = requests.Session()


def get_json(url: str, params: dict):
    for attempt in range(5):
        res = session.get(url, params=params, timeout=30)
        if res.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        res.raise_for_status()
        time.sleep(REQUEST_PAUSE_S)
        return res.json()
    raise RuntimeError(f"Still rate limited: {url}")


def day(ms: int) -> int:
    return ms // DAY_MS * DAY_MS // 1000


def bitstamp_btc_usd() -> dict[int, tuple]:
    bars: dict[int, tuple] = {}
    end = int(time.time())
    while True:
        page = get_json(
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/",
            {"step": 86400, "limit": 1000, "end": end},
        )["data"]["ohlc"]
        new = [b for b in page if int(b["timestamp"]) not in bars]
        if not new:
            return bars
        for b in new:
            t = int(b["timestamp"])
            bars[t] = tuple(float(b[k]) for k in ("open", "high", "low", "close", "volume"))
        end = min(int(b["timestamp"]) for b in page) - 1


def bitfinex(market: str) -> dict[int, tuple]:
    bars: dict[int, tuple] = {}
    start = 0
    while True:
        page = get_json(
            f"https://api-pub.bitfinex.com/v2/candles/trade:1D:{market}/hist",
            {"sort": 1, "limit": 10000, "start": start},
        )
        if not page:
            return bars
        for ms, o, c, h, lo, v in page:
            bars[day(ms)] = (o, h, lo, c, v)
        start = page[-1][0] + 1
        if len(page) < 10000:
            return bars


def poloniex(market: str) -> dict[int, tuple]:
    bars: dict[int, tuple] = {}
    start = int(datetime(2014, 1, 1, tzinfo=UTC).timestamp() * 1000)
    now = int(time.time() * 1000)
    while start < now:
        end = start + 500 * DAY_MS
        page = get_json(
            f"https://api.poloniex.com/markets/{market}/candles",
            {"interval": "DAY_1", "startTime": start, "endTime": end, "limit": 500},
        )
        for row in page:
            low, high, open_, close, _, quantity = (float(x) for x in row[:6])
            bars[day(int(row[12]))] = (open_, high, low, close, quantity)
        start = end
    return bars


def in_usd(coin_btc: tuple, btc_usd: tuple) -> tuple:
    o, h, lo, c = (a * b for a, b in zip(coin_btc[:4], btc_usd[:4]))
    return (o, max(h, o, c), min(lo, o, c), c, coin_btc[4])


def save(db: sqlite3.Connection, symbol: str, rows: list[tuple]) -> None:
    db.execute("DELETE FROM candles WHERE symbol = ? AND interval = '1d'", (symbol,))
    db.executemany(
        "INSERT INTO candles VALUES (?, '1d', ?, ?, ?, ?, ?, ?, ?)",
        [(symbol, t, *bar, source) for t, bar, source in rows],
    )
    db.commit()
    first, last = (datetime.fromtimestamp(rows[i][0], UTC).date() for i in (0, -1))
    print(f"{symbol}: {len(rows)} days, {first} to {last}")


def main() -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            time INTEGER NOT NULL,  -- start of the UTC day, Unix seconds
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,   -- in coins
            source TEXT NOT NULL,   -- which market(s) the bar came from
            PRIMARY KEY (symbol, interval, time)
        )"""
    )

    btc = bitstamp_btc_usd()
    save(db, "BTC-USD", [(t, btc[t], "bitstamp:btcusd") for t in sorted(btc)])

    for symbol, (polo_market, bfx_market) in COINS.items():
        direct = bitfinex(bfx_market)
        switch = min(direct)
        rows = []
        if polo_market:
            via_btc = poloniex(polo_market)
            source = f"poloniex:{polo_market}*bitstamp:btcusd"
            rows += [
                (t, in_usd(via_btc[t], btc[t]), source)
                for t in via_btc
                if t in btc and (t < switch or (t not in direct and t < max(direct)))
            ]
            seam = next((t for t in sorted(direct) if t in via_btc and t in btc), None)
            if seam:
                ratio = in_usd(via_btc[seam], btc[seam])[3] / direct[seam][3]
                print(f"  {symbol} seam {datetime.fromtimestamp(seam, UTC).date()}: converted/direct close = {ratio:.4f}")
        rows += [(t, direct[t], f"bitfinex:{bfx_market}") for t in direct]
        save(db, symbol, sorted(rows))

    db.close()
    print(f"Saved to {DB_PATH}")


if __name__ == "__main__":
    main()
