import pandas as pd

from app.indicators.base import Indicator, rma


class ADX(Indicator):
    id = "adx"
    name = "ADX / DMI"

    def __init__(self, di_length: int = 14, adx_smoothing: int = 14):
        self.di_length = di_length
        self.adx_smoothing = adx_smoothing

    @property
    def params(self):
        return {"di_length": self.di_length, "adx_smoothing": self.adx_smoothing}

    def lines(self, bars: pd.DataFrame):
        high, low, close = bars["high"], bars["low"], bars["close"]

        up = high.diff()
        down = -low.diff()
        plus_dm = up.where((up > down) & (up > 0), 0.0).where(up.notna())
        minus_dm = down.where((down > up) & (down > 0), 0.0).where(down.notna())

        prev_close = close.shift()
        true_range = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1, skipna=False)

        tr_smoothed = rma(true_range, self.di_length)
        plus_di = 100 * rma(plus_dm, self.di_length) / tr_smoothed
        minus_di = 100 * rma(minus_dm, self.di_length) / tr_smoothed

        di_sum = (plus_di + minus_di).replace(0, 1)
        dx = 100 * (plus_di - minus_di).abs() / di_sum
        adx = dx.rolling(self.adx_smoothing).mean()

        return {
            "adx": ("ADX", adx),
            "plus_di": ("+DI", plus_di),
            "minus_di": ("-DI", minus_di),
        }
