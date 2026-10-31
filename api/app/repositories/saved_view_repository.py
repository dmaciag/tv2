from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.saved_view import SavedView


class SavedViewRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[SavedView]:
        return list(self.db.scalars(select(SavedView).order_by(SavedView.updated_at.desc())))

    def get(self, view_id: int) -> SavedView | None:
        return self.db.get(SavedView, view_id)

    def upsert(self, ticker: str, interval: str, range_from: int, range_to: int) -> SavedView:
        view = self.db.scalar(
            select(SavedView).where(SavedView.ticker == ticker, SavedView.interval == interval)
        ) or SavedView(ticker=ticker, interval=interval)
        view.range_from = range_from
        view.range_to = range_to
        self.db.add(view)
        self.db.commit()
        self.db.refresh(view)
        return view

    def delete(self, view: SavedView) -> None:
        self.db.delete(view)
        self.db.commit()
