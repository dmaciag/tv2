from sqlalchemy.orm import Session

from app.models.chart_state import ChartView, PanelChart


class ChartStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_view(self, ticker: str, interval: str) -> ChartView | None:
        return self.db.get(ChartView, (ticker, interval))

    def upsert_view(self, ticker: str, interval: str, range_from: int, range_to: int) -> ChartView:
        view = self.get_view(ticker, interval) or ChartView(ticker=ticker, interval=interval)
        view.range_from = range_from
        view.range_to = range_to
        self.db.add(view)
        self.db.commit()
        self.db.refresh(view)
        return view

    def get_panel(self, panel: str) -> PanelChart | None:
        return self.db.get(PanelChart, panel)

    def set_panel(self, panel: str, ticker: str, interval: str) -> PanelChart:
        row = self.get_panel(panel) or PanelChart(panel=panel)
        row.ticker = ticker
        row.interval = interval
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
