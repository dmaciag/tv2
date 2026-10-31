from datetime import datetime

from app.schemas.chart_state import ChartRef, TimeRange


class SavedViewWrite(ChartRef, TimeRange):
    pass


class SavedViewRead(SavedViewWrite):
    id: int
    updated_at: datetime
