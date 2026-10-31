from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.arithmetic.expression import ExpressionError
from app.routers.symbol_router import (
    FORCE_DESCRIPTION,
    Interval,
    get_indicator_service,
    get_symbol_service,
)
from app.schemas.indicator import ChartData
from app.schemas.symbol import CandleSeries
from app.services.arithmetic_service import ArithmeticService, NoOverlapError
from app.services.indicator_service import IndicatorService, UnknownIndicatorError
from app.services.symbol_service import InvalidTickerError, NoMarketDataError, SymbolService

router = APIRouter(prefix="/api/arithmetic", tags=["arithmetic"])

FORMULA_QUERY = Query(
    ...,
    min_length=1,
    max_length=200,
    description="Tickers combined with * / ^ and parentheses",
    examples=["TTD / (AAPL^0.5 * TEAM^0.25 * MSFT^0.25)"],
)
FORCE_FORMULA_DESCRIPTION = f"{FORCE_DESCRIPTION} for every ticker, then recompute the formula"


def get_arithmetic_service(
    symbol_service: SymbolService = Depends(get_symbol_service),
) -> ArithmeticService:
    return ArithmeticService(symbol_service)


def _load(service: ArithmeticService, formula, interval, start, end, force) -> CandleSeries:
    try:
        return service.get_candles(formula, interval, start, end, force)
    except ExpressionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid formula: {e}")
    except InvalidTickerError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid ticker: {e}")
    except NoMarketDataError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No market data for {e}")
    except NoOverlapError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No bars shared by all of: {e}")


@router.get("/candles", response_model=CandleSeries)
def get_candles(
    formula: str = FORMULA_QUERY,
    interval: Interval = "1d",
    start: date | None = None,
    end: date | None = None,
    force: bool = Query(False, description=FORCE_FORMULA_DESCRIPTION),
    service: ArithmeticService = Depends(get_arithmetic_service),
):
    return _load(service, formula, interval, start, end, force)


@router.get("/chart", response_model=ChartData)
def get_chart(
    formula: str = FORMULA_QUERY,
    interval: Interval = "1d",
    indicators: list[str] = Query(["adx", "macd"], description="Indicator ids to calculate"),
    start: date | None = None,
    end: date | None = None,
    force: bool = Query(False, description=FORCE_FORMULA_DESCRIPTION),
    service: ArithmeticService = Depends(get_arithmetic_service),
    indicator_service: IndicatorService = Depends(get_indicator_service),
):
    series = _load(service, formula, interval, start, end, force)
    try:
        results = indicator_service.calculate(series.candles, indicators)
    except UnknownIndicatorError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown indicator(s): {e}. Available: {', '.join(indicator_service.available())}",
        )
    return ChartData(**series.model_dump(), indicators=results)
