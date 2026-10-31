from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.symbol_repository import SymbolRepository
from app.schemas.indicator import ChartData
from app.schemas.symbol import CandleSeries, SymbolCreate, SymbolRead, SymbolUpdate
from app.services.indicator_service import IndicatorService, UnknownIndicatorError
from app.services.symbol_service import (
    InvalidTickerError,
    NoMarketDataError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
    SymbolService,
)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])

Interval = Literal[
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"
]

FORCE_DESCRIPTION = "Re-download from yfinance and overwrite the JSON cache"


def get_symbol_service(db: Session = Depends(get_db)) -> SymbolService:
    return SymbolService(SymbolRepository(db))


def get_indicator_service() -> IndicatorService:
    return IndicatorService()


def _load_candles(service: SymbolService, ticker, interval, start, end, force) -> CandleSeries:
    try:
        return service.get_candles(ticker, interval, start, end, force)
    except InvalidTickerError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid ticker")
    except NoMarketDataError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No market data for that ticker/range")


@router.get("/{ticker}/candles", response_model=CandleSeries)
def get_candles(
    ticker: str,
    interval: Interval = "1d",
    start: date | None = Query(None, examples=["1995-01-01"]),
    end: date | None = None,
    force: bool = Query(False, description=FORCE_DESCRIPTION),
    service: SymbolService = Depends(get_symbol_service),
):
    return _load_candles(service, ticker, interval, start, end, force)


@router.get("/{ticker}/chart", response_model=ChartData)
def get_chart(
    ticker: str,
    interval: Interval = "1d",
    indicators: list[str] = Query(["adx", "macd"], description="Indicator ids to calculate"),
    start: date | None = Query(None, examples=["1995-01-01"]),
    end: date | None = None,
    force: bool = Query(False, description=FORCE_DESCRIPTION),
    service: SymbolService = Depends(get_symbol_service),
    indicator_service: IndicatorService = Depends(get_indicator_service),
):
    series = _load_candles(service, ticker, interval, start, end, force)
    try:
        results = indicator_service.calculate(series.candles, indicators)
    except UnknownIndicatorError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown indicator(s): {e}. Available: {', '.join(indicator_service.available())}",
        )
    return ChartData(**series.model_dump(), indicators=results)


@router.get("", response_model=list[SymbolRead])
def list_symbols(service: SymbolService = Depends(get_symbol_service)):
    return service.list_symbols()


@router.get("/{symbol_id}", response_model=SymbolRead)
def get_symbol(symbol_id: int, service: SymbolService = Depends(get_symbol_service)):
    try:
        return service.get_symbol(symbol_id)
    except SymbolNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Symbol not found")


@router.post("", response_model=SymbolRead, status_code=status.HTTP_201_CREATED)
def create_symbol(data: SymbolCreate, service: SymbolService = Depends(get_symbol_service)):
    try:
        return service.create_symbol(data)
    except SymbolAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ticker already exists")


@router.patch("/{symbol_id}", response_model=SymbolRead)
def update_symbol(
    symbol_id: int, data: SymbolUpdate, service: SymbolService = Depends(get_symbol_service)
):
    try:
        return service.update_symbol(symbol_id, data)
    except SymbolNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Symbol not found")


@router.delete("/{symbol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symbol(symbol_id: int, service: SymbolService = Depends(get_symbol_service)):
    try:
        service.delete_symbol(symbol_id)
    except SymbolNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Symbol not found")
