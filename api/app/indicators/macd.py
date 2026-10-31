import pandas as pd

from app.indicators.base import Indicator, ema


class MACD(Indicator):
    id = "macd"
    name = "MACD"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    @property
    def params(self):
        return {"fast": self.fast, "slow": self.slow, "signal": self.signal}

    def lines(self, bars: pd.DataFrame):
        close = bars["close"]
        macd = ema(close, self.fast) - ema(close, self.slow)
        signal = ema(macd, self.signal)
        return {
            "macd": ("MACD", macd),
            "signal": ("Signal", signal),
        }
