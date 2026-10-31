from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from app.schemas.indicator import IndicatorLine, IndicatorPoint, IndicatorResult


class Indicator(ABC):
    id: ClassVar[str]
    name: ClassVar[str]

    @property
    def params(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def lines(self, bars: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
        ...

    def calculate(self, bars: pd.DataFrame) -> IndicatorResult:
        return IndicatorResult(
            id=self.id,
            name=self.name,
            params=self.params,
            lines=[
                IndicatorLine(key=key, label=label, values=_points(series))
                for key, (label, series) in self.lines(bars).items()
            ],
        )


def _points(series: pd.Series) -> list[IndicatorPoint]:
    series = series.dropna()
    return [IndicatorPoint(time=int(t), value=float(v)) for t, v in series.items()]


def _seeded_average(series: pd.Series, length: int, alpha: float) -> pd.Series:
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < length:
        return pd.Series(out, index=series.index)

    start = valid[0] + length - 1
    out[start] = values[valid[0] : start + 1].mean()
    for i in range(start + 1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=series.index)


def ema(series: pd.Series, length: int) -> pd.Series:
    return _seeded_average(series, length, 2 / (length + 1))


def rma(series: pd.Series, length: int) -> pd.Series:
    return _seeded_average(series, length, 1 / length)
