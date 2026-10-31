from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import StateBase


class SavedView(StateBase):
    __tablename__ = "saved_views"
    __table_args__ = (UniqueConstraint("ticker", "interval"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(200))
    interval: Mapped[str] = mapped_column(String(8))
    range_from: Mapped[int] = mapped_column(Integer)
    range_to: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
