import pandas as pd

from app.indicators import INDICATORS, Indicator
from app.schemas.indicator import IndicatorResult
from app.schemas.symbol import Candle


class UnknownIndicatorError(Exception):
    pass


class IndicatorService:
    def __init__(self, registry: dict[str, type[Indicator]] = INDICATORS):
        self.registry = registry

    def available(self) -> list[str]:
        return list(self.registry)

    def calculate(self, candles: list[Candle], indicator_ids: list[str]) -> list[IndicatorResult]:
        unknown = [i for i in indicator_ids if i not in self.registry]
        if unknown:
            raise UnknownIndicatorError(", ".join(unknown))

        bars = pd.DataFrame(
            [c.model_dump() for c in candles],
            columns=["time", "open", "high", "low", "close", "volume"],
        ).set_index("time")
        return [self.registry[i]().calculate(bars) for i in indicator_ids]
