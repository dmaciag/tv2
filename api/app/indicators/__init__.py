from app.indicators.adx import ADX
from app.indicators.base import Indicator
from app.indicators.macd import MACD

INDICATORS: dict[str, type[Indicator]] = {cls.id: cls for cls in (ADX, MACD)}
