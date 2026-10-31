import sqlite3
from contextlib import closing
from pathlib import Path

CRYPTO_DB = Path(__file__).resolve().parents[2] / "crypto.db"


class CryptoHistoryRepository:
    def __init__(self, path: Path = CRYPTO_DB):
        self.path = path

    def daily_before(self, symbol: str, before: int) -> list[tuple[int, float, float, float, float, float]]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)) as db:
            return db.execute(
                "SELECT time, open, high, low, close, volume FROM candles"
                " WHERE symbol = ? AND interval = '1d' AND time < ? ORDER BY time",
                (symbol, before),
            ).fetchall()
