from pydantic import BaseModel, Field

from app.schemas.symbol import Candle


class FractalRequest(BaseModel):
    candles: list[Candle] = Field(..., min_length=1, description="Bars in time order")


class FractalBox(BaseModel):
    start: int = Field(..., description="First bar's time, Unix seconds")
    end: int = Field(..., description="Last bar's time, Unix seconds")
    low: float
    high: float


class FractalMatch(BaseModel):
    small: FractalBox
    big: FractalBox
    correlation: float = Field(..., description="How closely the two shapes match, up to 1")
    time_scale: float = Field(..., description="How many times longer the big copy lasts")
    price_scale: float = Field(..., description="How many times larger the big copy's move is")
