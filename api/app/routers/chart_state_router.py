from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_state_db
from app.repositories.chart_state_repository import ChartStateRepository
from app.schemas.chart_state import ChartRef, TimeRange
from app.services.chart_state_service import ChartStateNotFoundError, ChartStateService

router = APIRouter(prefix="/api/chart-state", tags=["chart state"])


def get_chart_state_service(db: Session = Depends(get_state_db)) -> ChartStateService:
    return ChartStateService(ChartStateRepository(db))


PanelId = Annotated[str, Path(min_length=1, max_length=16, examples=["left", "right"])]


@router.get("/panels/{panel}", response_model=ChartRef)
def get_panel(panel: PanelId, service: ChartStateService = Depends(get_chart_state_service)):
    try:
        return service.get_panel(panel)
    except ChartStateNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No chart opened in that panel yet")


@router.put("/panels/{panel}", response_model=ChartRef)
def set_panel(
    panel: PanelId, data: ChartRef, service: ChartStateService = Depends(get_chart_state_service)
):
    return service.set_panel(panel, data)


TickerQuery = Annotated[str, Query(min_length=1, max_length=200, description="Ticker or formula")]
IntervalQuery = Annotated[str, Query(min_length=1, max_length=8, examples=["1wk"])]


@router.get("/views", response_model=TimeRange)
def get_view(
    ticker: TickerQuery,
    interval: IntervalQuery,
    service: ChartStateService = Depends(get_chart_state_service),
):
    try:
        return service.get_view(ticker, interval)
    except ChartStateNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No saved view for that chart")


@router.put("/views", response_model=TimeRange)
def save_view(
    ticker: TickerQuery,
    interval: IntervalQuery,
    data: TimeRange,
    service: ChartStateService = Depends(get_chart_state_service),
):
    return service.save_view(ticker, interval, data)
