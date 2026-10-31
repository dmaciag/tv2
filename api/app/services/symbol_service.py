import re
import warnings
from datetime import UTC, date, datetime

import pandas as pd
import yfinance as yf

from app.models.symbol import Symbol
from app.repositories.candle_cache_repository import CandleCacheRepository
from app.repositories.crypto_history_repository import CryptoHistoryRepository
from app.repositories.symbol_repository import SymbolRepository
from app.schemas.symbol import Candle, CandleSeries, SymbolCreate, SymbolUpdate
from app.tickers import resolve_ticker


class SymbolNotFoundError(Exception):
    pass


class SymbolAlreadyExistsError(Exception):
    pass


class NoMarketDataError(Exception):
    pass


class InvalidTickerError(Exception):
    pass


TICKER_PATTERN = re.compile(r"^\^?[A-Z0-9][A-Z0-9.=-]{0,15}$")

MAX_PERIOD = {"1m": "7d", "60m": "730d", "1h": "730d"}
INTRADAY = {"2m", "5m", "15m", "30m", "90m"}

HOURS_PER_4H_BAR = 4

BACKFILL_INTERVALS = {"1d", "1wk", "1mo", "3mo"}
SECONDS_PER_DAY = 86_400

warnings.filterwarnings("ignore", module="yfinance")


class SymbolService:
    def __init__(
        self,
        repository: SymbolRepository,
        cache: CandleCacheRepository | None = None,
        crypto_history: CryptoHistoryRepository | None = None,
    ):
        self.repository = repository
        self.cache = cache or CandleCacheRepository()
        self.crypto_history = crypto_history or CryptoHistoryRepository()

    def list_symbols(self) -> list[Symbol]:
        return self.repository.list()

    def get_symbol(self, symbol_id: int) -> Symbol:
        symbol = self.repository.get(symbol_id)
        if symbol is None:
            raise SymbolNotFoundError(symbol_id)
        return symbol

    def create_symbol(self, data: SymbolCreate) -> Symbol:
        ticker = data.ticker.strip().upper()
        if self.repository.get_by_ticker(ticker):
            raise SymbolAlreadyExistsError(ticker)
        symbol = Symbol(**data.model_dump(exclude={"ticker"}), ticker=ticker)
        return self.repository.create(symbol)

    def update_symbol(self, symbol_id: int, data: SymbolUpdate) -> Symbol:
        symbol = self.get_symbol(symbol_id)
        return self.repository.update(symbol, data.model_dump(exclude_unset=True))

    def delete_symbol(self, symbol_id: int) -> None:
        self.repository.delete(self.get_symbol(symbol_id))

    def get_candles(
        self,
        ticker: str,
        interval: str,
        start: date | None = None,
        end: date | None = None,
        force: bool = False,
    ) -> CandleSeries:
        ticker = resolve_ticker(ticker)
        if not TICKER_PATTERN.match(ticker):
            raise InvalidTickerError(ticker)

        cached = None if force else self.cache.load(ticker, interval)
        if cached:
            candles, fetched_at = cached
            source = "cache"
        else:
            candles = self._backfill(ticker, interval, self._download(ticker, interval))
            fetched_at = datetime.now(UTC)
            self.cache.save(ticker, interval, candles, fetched_at)
            source = "yfinance"

        if start or end:
            candles = [c for c in candles if in_date_range(c.time, start, end)]
            if not candles:
                raise NoMarketDataError(ticker)

        return CandleSeries(
            ticker=ticker, interval=interval, source=source, fetched_at=fetched_at, candles=candles
        )

    def _backfill(self, ticker: str, interval: str, candles: list[Candle]) -> list[Candle]:
        if interval not in BACKFILL_INTERVALS or len(candles) < 2:
            return candles
        keep = candles if interval == "1d" else candles[1:]
        days = self.crypto_history.daily_before(ticker, keep[0].time)
        if not days:
            return candles
        return _days_to_bars(days, interval, anchor=keep[0].time) + keep

    def _download(self, ticker: str, interval: str) -> list[Candle]:
        source_interval = "1h" if interval == "4h" else interval
        period = MAX_PERIOD.get(source_interval, "60d" if source_interval in INTRADAY else "max")
        df = yf.download(
            ticker,
            period=period,
            interval=source_interval,
            auto_adjust=False,
            prepost=False,
            multi_level_index=False,
            progress=False,
        )
        if df is None or df.empty:
            raise NoMarketDataError(ticker)

        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if interval == "4h":
            df = _hourly_to_4h(df)
        return [
            Candle(
                time=int(ts.timestamp()),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                adj_close=row["Adj Close"],
                volume=0 if pd.isna(row["Volume"]) else int(row["Volume"]),
            )
            for ts, row in df.iterrows()
        ]


def _hourly_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    day = df.index.date
    slot = df.groupby(day).cumcount() // HOURS_PER_4H_BAR
    bars = df.assign(Time=df.index).groupby([day, slot]).agg(
        Time=("Time", "first"),
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        **{"Adj Close": ("Adj Close", "last")},
        Volume=("Volume", "sum"),
    )
    return bars.set_index("Time")


def _month_index(day_start: int) -> int:
    d = datetime.fromtimestamp(day_start, UTC)
    return d.year * 12 + d.month - 1


def _days_to_bars(days: list[tuple], interval: str, anchor: int) -> list[Candle]:
    anchor_month = _month_index(anchor)

    def period_start(t: int) -> int:
        if interval == "1d":
            return t
        if interval == "1wk":
            day = t // SECONDS_PER_DAY
            return (day - (day + 3) % 7) * SECONDS_PER_DAY
        months = 3 if interval == "3mo" else 1
        m = anchor_month + (_month_index(t) - anchor_month) // months * months
        return int(datetime(m // 12, m % 12 + 1, 1, tzinfo=UTC).timestamp())

    bars: dict[int, Candle] = {}
    for t, o, h, lo, c, coins in days:
        volume = int(coins * (h + lo + c) / 3)
        start = period_start(t)
        bar = bars.get(start)
        if bar is None:
            bars[start] = Candle(time=start, open=o, high=h, low=lo, close=c, adj_close=c, volume=volume)
        else:
            bar.high, bar.low = max(bar.high, h), min(bar.low, lo)
            bar.close = bar.adj_close = c
            bar.volume += volume
    return list(bars.values())


def in_date_range(timestamp: int, start: date | None, end: date | None) -> bool:
    day = datetime.fromtimestamp(timestamp, UTC).date()
    return (start is None or day >= start) and (end is None or day < end)
