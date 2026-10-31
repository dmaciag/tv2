from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.symbol import Symbol


class SymbolRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[Symbol]:
        return list(self.db.scalars(select(Symbol).order_by(Symbol.ticker)))

    def get(self, symbol_id: int) -> Symbol | None:
        return self.db.get(Symbol, symbol_id)

    def get_by_ticker(self, ticker: str) -> Symbol | None:
        return self.db.scalar(select(Symbol).where(Symbol.ticker == ticker))

    def create(self, symbol: Symbol) -> Symbol:
        self.db.add(symbol)
        self.db.commit()
        self.db.refresh(symbol)
        return symbol

    def update(self, symbol: Symbol, fields: dict) -> Symbol:
        for key, value in fields.items():
            setattr(symbol, key, value)
        self.db.commit()
        self.db.refresh(symbol)
        return symbol

    def delete(self, symbol: Symbol) -> None:
        self.db.delete(symbol)
        self.db.commit()
