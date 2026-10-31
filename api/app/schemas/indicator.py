from typing import Any

from pydantic import BaseModel, Field

from app.schemas.symbol import Candle, CandleSeries


class IndicatorPoint(BaseModel):
    time: int
    value: float


class IndicatorLine(BaseModel):
    key: str
    label: str
    values: list[IndicatorPoint]


class IndicatorResult(BaseModel):
    id: str
    name: str
    params: dict[str, Any]
    lines: list[IndicatorLine]


class ChartData(CandleSeries):
    indicators: list[IndicatorResult]


class IndicatorRequest(BaseModel):
    candles: list[Candle] = Field(..., min_length=1, description="Bars in time order")
    indicators: list[str] = Field(["adx", "macd"], description="Indicator ids to calculate")
