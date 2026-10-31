from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.indicator import IndicatorResult
from app.schemas.symbol import Candle

Variation = Literal["realistic", "strong", "maximum"]


class ExplodeScenario(BaseModel):
    id: str
    name: str
    description: str
    candles: list[Candle]
    indicators: list[IndicatorResult]
    max_ohlc_error: float = Field(
        ...,
        description="Largest difference between the original bars and these bars re-aggregated. "
        "0 means identical OHLC, so the higher-timeframe indicators are identical too.",
    )


class ExplodeCandlesRequest(BaseModel):
    symbol: str = Field(
        ..., min_length=1, max_length=200, description="Ticker or formula; picks the trading calendar"
    )
    interval: str
    candles: list[Candle] = Field(..., min_length=1)
    from_time: int
    to_time: int
    indicators: list[str] = ["adx", "macd"]
    scenarios: list[str] | None = Field(None, description="Scenario ids to run; all when omitted")
    variation: Variation = "realistic"


class ExplodeResult(BaseModel):
    ticker: str
    interval: str
    sub_interval: str
    market: str = Field(..., description="Trading calendar used: stock, crypto or fx")
    from_time: int = Field(..., description="First exploded bar, Unix seconds")
    to_time: int = Field(..., description="Last exploded bar, Unix seconds")
    parent_bars: int
    variation: Variation
    scenarios: list[ExplodeScenario]
