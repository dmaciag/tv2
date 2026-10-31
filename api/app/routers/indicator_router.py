from fastapi import APIRouter, Depends, HTTPException, status

from app.routers.symbol_router import get_indicator_service
from app.schemas.indicator import IndicatorRequest, IndicatorResult
from app.services.indicator_service import IndicatorService, UnknownIndicatorError

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.post("", response_model=list[IndicatorResult])
def calculate_indicators(
    data: IndicatorRequest, service: IndicatorService = Depends(get_indicator_service)
):
    try:
        return service.calculate(data.candles, data.indicators)
    except UnknownIndicatorError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown indicator(s): {e}. Available: {', '.join(service.available())}",
        )
