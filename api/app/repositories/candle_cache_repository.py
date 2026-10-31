import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.schemas.symbol import Candle

CACHE_DIR = Path(__file__).resolve().parents[2] / "json_data"


class CandleCacheRepository:
    def __init__(self, root: Path = CACHE_DIR):
        self.root = root

    def _path(self, ticker: str, interval: str) -> Path:
        return self.root / ticker / f"{interval}.json"

    def load(self, ticker: str, interval: str) -> tuple[list[Candle], datetime] | None:
        path = self._path(ticker, interval)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        candles = [Candle(**c) for c in data["candles"]]
        return candles, datetime.fromisoformat(data["fetched_at"])

    def save(self, ticker: str, interval: str, candles: list[Candle], fetched_at: datetime) -> None:
        path = self._path(ticker, interval)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ticker": ticker,
            "interval": interval,
            "fetched_at": fetched_at.isoformat(),
            "candles": [c.model_dump() for c in candles],
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)


class CompositeCacheRepository(CandleCacheRepository):
    def __init__(self, root: Path = CACHE_DIR / "_composite"):
        super().__init__(root)

    VERSION = 2

    def _path(self, formula: str, interval: str) -> Path:
        key = f"v{self.VERSION}:{formula}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        return self.root / digest / f"{interval}.json"
