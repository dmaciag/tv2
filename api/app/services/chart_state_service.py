from app.arithmetic.expression import normalize
from app.models.chart_state import ChartView, PanelChart
from app.repositories.chart_state_repository import ChartStateRepository
from app.schemas.chart_state import ChartRef, TimeRange


class ChartStateNotFoundError(Exception):
    pass


class ChartStateService:
    def __init__(self, repository: ChartStateRepository):
        self.repository = repository

    def get_view(self, ticker: str, interval: str) -> ChartView:
        view = self.repository.get_view(normalize(ticker), interval)
        if view is None:
            raise ChartStateNotFoundError(ticker, interval)
        return view

    def save_view(self, ticker: str, interval: str, data: TimeRange) -> ChartView:
        return self.repository.upsert_view(
            normalize(ticker), interval, data.range_from, data.range_to
        )

    def get_panel(self, panel: str) -> PanelChart:
        row = self.repository.get_panel(panel)
        if row is None:
            raise ChartStateNotFoundError(panel)
        return row

    def set_panel(self, panel: str, data: ChartRef) -> PanelChart:
        return self.repository.set_panel(panel, normalize(data.ticker), data.interval)
