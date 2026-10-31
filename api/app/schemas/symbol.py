from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SymbolBase(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    name: str = Field(..., min_length=1, max_length=128, examples=["Apple Inc."])
    exchange: str = Field(..., min_length=1, max_length=32, examples=["NASDAQ"])
    price: float = Field(0.0, ge=0)


class SymbolCreate(SymbolBase):
    pass


class SymbolUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    exchange: str | None = Field(None, min_length=1, max_length=32)
    price: float | None = Field(None, ge=0)


class SymbolRead(SymbolBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class Candle(BaseModel):
    time: int = Field(..., description="Bar open time, Unix seconds (UTC)")
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class CandleSeries(BaseModel):
    ticker: str
    interval: str
    source: Literal["cache", "yfinance", "computed"]
    fetched_at: datetime = Field(
        ..., description="When the bars were downloaded from yfinance (or computed, for formulas)"
    )
    candles: list[Candle]
