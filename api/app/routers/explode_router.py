from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.arithmetic.expression import ExpressionError
from app.routers.symbol_router import Interval, get_indicator_service, get_symbol_service
from app.schemas.explode import ExplodeCandlesRequest, ExplodeResult, Variation
from app.services.arithmetic_service import ArithmeticService, NoOverlapError
from app.services.explode_service import (
    ExplodeNotSupportedError,
    ExplodeService,
    TooManyBarsError,
    UnknownScenarioError,
)
from app.services.indicator_service import IndicatorService, UnknownIndicatorError
from app.services.symbol_service import InvalidTickerError, NoMarketDataError, SymbolService

router = APIRouter(prefix="/api/explode", tags=["explode"])


def get_explode_service(
    symbol_service: SymbolService = Depends(get_symbol_service),
    indicator_service: IndicatorService = Depends(get_indicator_service),
) -> ExplodeService:
    return ExplodeService(symbol_service, ArithmeticService(symbol_service), indicator_service)


@router.get("", response_model=ExplodeResult)
def explode(
    symbol: str = Query(..., min_length=1, max_length=200, description="Ticker or formula"),
    interval: Interval = "1wk",
    from_time: int = Query(..., description="First visible bar, Unix seconds"),
    to_time: int = Query(..., description="Last visible bar, Unix seconds"),
    indicators: list[str] = Query(["adx", "macd"], description="Indicator ids to calculate"),
    variation: Variation = Query(
        "realistic", description="realistic candles, or strong/maximum MACD separation"
    ),
    service: ExplodeService = Depends(get_explode_service),
):
    with _explode_errors(interval):
        return service.explode(symbol, interval, from_time, to_time, indicators, variation)


@router.post("/candles", response_model=ExplodeResult)
def explode_candles(
    request: ExplodeCandlesRequest, service: ExplodeService = Depends(get_explode_service)
):
    with _explode_errors(request.interval):
        return service.explode_candles(
            request.symbol,
            request.interval,
            request.candles,
            request.from_time,
            request.to_time,
            request.indicators,
            request.scenarios,
            request.variation,
        )


@contextmanager
def _explode_errors(interval: str):
    try:
        yield
    except ExplodeNotSupportedError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Explode isn't available for {interval}")
    except TooManyBarsError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{e.visible} bars are visible; zoom in to {e.allowed} or fewer to explode",
        )
    except (ExpressionError, InvalidTickerError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid symbol: {e}")
    except UnknownIndicatorError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown indicator(s): {e}")
    except UnknownScenarioError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown scenario(s): {e}")
    except NoMarketDataError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No market data for {e} in that range")
    except NoOverlapError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No bars shared by all of: {e}")
