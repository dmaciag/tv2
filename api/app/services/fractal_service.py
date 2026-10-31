import numpy as np

from app.schemas.fractal import FractalBox, FractalMatch
from app.schemas.symbol import Candle

SHAPE_POINTS = 32
MIN_BARS = 8
MIN_BAR_SHARE = 1 / 40
LENGTH_GROWTH = 1.15
STARTS_PER_LENGTH = 12
MAX_STARTS = 400
MIN_TIME_SCALE = 2.0
MIN_SHAPE = 0.25
MIN_CORRELATION = 0.85


class NoFractalError(Exception):
    pass


class FractalService:
    def find(self, candles: list[Candle]) -> FractalMatch:
        n = len(candles)
        min_bars = max(MIN_BARS, round(n * MIN_BAR_SHARE))
        if n < min_bars * (1 + MIN_TIME_SCALE):
            raise NoFractalError(f"Need at least {round(min_bars * (1 + MIN_TIME_SCALE))} bars")

        log_close = np.log([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])

        starts, lengths = _windows(n, min_bars)
        shapes = np.array([_shape(log_close[s : s + w]) for s, w in zip(starts, lengths)])
        ramp = _shape(np.arange(SHAPE_POINTS, dtype=float))
        has_shape = 1 - (shapes @ ramp) ** 2 >= MIN_SHAPE
        moves = np.array(
            [np.log(highs[s : s + w].max() / lows[s : s + w].min()) for s, w in zip(starts, lengths)]
        )
        ends = starts + lengths

        best = None
        for big_length in np.unique(lengths):
            big = np.flatnonzero((lengths == big_length) & has_shape)
            small = np.flatnonzero((lengths * MIN_TIME_SCALE <= big_length) & has_shape)
            if big.size == 0 or small.size == 0:
                continue
            correlation = shapes[small] @ shapes[big].T
            apart = (ends[small][:, None] <= starts[big]) | (ends[big] <= starts[small][:, None])
            correlation[~apart | (moves[big] <= moves[small][:, None])] = -np.inf
            i, j = np.unravel_index(np.argmax(correlation), correlation.shape)
            if best is None or correlation[i, j] > best[0]:
                best = (float(correlation[i, j]), small[i], big[j])

        if best is None or best[0] < MIN_CORRELATION:
            raise NoFractalError("No pattern in these bars repeats at a larger scale")

        corr, s, b = best

        def box(k: int) -> FractalBox:
            first, last = starts[k], ends[k] - 1
            return FractalBox(
                start=candles[first].time,
                end=candles[last].time,
                low=float(lows[first : last + 1].min()),
                high=float(highs[first : last + 1].max()),
            )

        return FractalMatch(
            small=box(s),
            big=box(b),
            correlation=corr,
            time_scale=float(lengths[b] / lengths[s]),
            price_scale=float(moves[b] / moves[s]),
        )


def _windows(n: int, min_bars: int) -> tuple[np.ndarray, np.ndarray]:
    starts, lengths = [], []
    length = min_bars
    while length <= n - min_bars:
        step = max(1, round(length / STARTS_PER_LENGTH), (n - length) // MAX_STARTS)
        for start in range(0, n - length + 1, step):
            starts.append(start)
            lengths.append(length)
        length = max(length + 1, round(length * LENGTH_GROWTH))
    return np.array(starts), np.array(lengths)


def _shape(values: np.ndarray) -> np.ndarray:
    resampled = np.interp(np.linspace(0, len(values) - 1, SHAPE_POINTS), np.arange(len(values)), values)
    centered = resampled - resampled.mean()
    norm = np.linalg.norm(centered)
    return centered / norm if norm > 0 else centered
