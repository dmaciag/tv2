from bisect import bisect_right
from datetime import UTC, date, datetime

import numpy as np

from app.arithmetic.expression import ExpressionError, Node, normalize, parse
from app.repositories.candle_cache_repository import CompositeCacheRepository
from app.schemas.symbol import Candle, CandleSeries
from app.services.symbol_service import NoMarketDataError, SymbolService, in_date_range

SECONDS_PER_DAY = 86_400

DAILY_OR_LONGER = {"1d", "5d", "1wk", "1mo", "3mo"}

BUILT_FROM = {"5d": "1d", "1wk": "1d", "1mo": "1d", "3mo": "1d", "4h": "1h"}


class NoOverlapError(Exception):
    pass


class ArithmeticService:
    def __init__(self, symbol_service: SymbolService, cache: CompositeCacheRepository | None = None):
        self.symbol_service = symbol_service
        self.cache = cache or CompositeCacheRepository()

    def get_candles(
        self,
        formula: str,
        interval: str,
        start: date | None = None,
        end: date | None = None,
        force: bool = False,
    ) -> CandleSeries:
        formula = normalize(formula)
        node = parse(formula)
        if not node.tickers():
            raise ExpressionError("Formula needs at least one ticker")

        cached = None if force else self.cache.load(formula, interval)
        if cached:
            candles, fetched_at = cached
            source = "cache"
        else:
            candles, fetched_at = self._compute(node, interval, force)
            self.cache.save(formula, interval, candles, fetched_at)
            source = "computed"

        if start or end:
            candles = [c for c in candles if in_date_range(c.time, start, end)]
            if not candles:
                raise NoMarketDataError(formula)

        return CandleSeries(
            ticker=formula, interval=interval, source=source, fetched_at=fetched_at, candles=candles
        )

    def _compute(self, node: Node, interval: str, force: bool):
        base = BUILT_FROM.get(interval)
        if base is None:
            return self._combine(node, interval, force), datetime.now(UTC)

        starts = [c.time for c in self._combine(node, interval, force)]
        groups: dict[int, list[Candle]] = {}
        for bar in self._combine(node, base, force):
            i = bisect_right(starts, bar.time) - 1
            if i >= 0:
                groups.setdefault(starts[i], []).append(bar)
        candles = [
            Candle(
                time=start,
                open=bars[0].open,
                high=max(b.high for b in bars),
                low=min(b.low for b in bars),
                close=bars[-1].close,
                adj_close=bars[-1].adj_close,
                volume=0,
            )
            for start, bars in sorted(groups.items())
        ]
        return candles, datetime.now(UTC)

    def _combine(self, node: Node, interval: str, force: bool) -> list[Candle]:
        daily = interval in DAILY_OR_LONGER

        def bar_key(timestamp: int) -> int:
            return round(timestamp / SECONDS_PER_DAY) if daily else timestamp

        series = {
            ticker: self.symbol_service.get_candles(ticker, interval, force=force)
            for ticker in sorted(node.tickers())
        }
        by_key = {t: {bar_key(c.time): c for c in s.candles} for t, s in series.items()}

        common = sorted(set.intersection(*(set(bars) for bars in by_key.values())))
        if not common:
            raise NoOverlapError(", ".join(series))

        def column(field: str) -> dict[str, np.ndarray]:
            return {
                t: np.array([getattr(bars[k], field) for k in common], dtype=float)
                for t, bars in by_key.items()
            }

        with np.errstate(divide="ignore", invalid="ignore"):
            opens = node.value_of(column("open"))
            closes = node.value_of(column("close"))
            adj_closes = node.value_of(column("adj_close"))
            of_highs = node.value_of(column("high"))
            of_lows = node.value_of(column("low"))
        prices = [of_highs, of_lows, opens, closes]
        high = np.fmax.reduce(prices)
        low = np.fmin.reduce(prices)

        candles = [
            Candle(
                time=key * SECONDS_PER_DAY if daily else key,
                open=o,
                high=h,
                low=lo,
                close=c,
                adj_close=a,
                volume=0,
            )
            for key, o, h, lo, c, a in zip(common, opens, high, low, closes, adj_closes)
            if np.isfinite([o, h, lo, c, a]).all()
        ]
        if not candles:
            raise NoOverlapError(", ".join(series))
        return candles
