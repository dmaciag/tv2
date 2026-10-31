import calendar
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY = 86_400

SUB_INTERVAL = {"3mo": "1mo", "1wk": "1d", "1d": "4h", "4h": "1h"}


@dataclass(frozen=True)
class Market:
    name: str
    tz: ZoneInfo
    session_open: time | None
    session_hours: float
    weekdays: int


MARKETS = {
    "stock": Market("stock", ZoneInfo("America/New_York"), time(9, 30), 6.5, 5),
    "crypto": Market("crypto", ZoneInfo("UTC"), None, 24, 7),
    "fx": Market("fx", ZoneInfo("Europe/London"), None, 24, 5),
}

_CRYPTO = re.compile(r"-(USD|USDT|USDC|EUR|GBP|JPY|BTC|ETH)$")


def market_of(tickers: set[str]) -> Market:
    if tickers and all(_CRYPTO.search(t) for t in tickers):
        return MARKETS["crypto"]
    if tickers and all(t.endswith("=X") for t in tickers):
        return MARKETS["fx"]
    return MARKETS["stock"]


@dataclass(frozen=True)
class SubBar:
    stamp: int
    hours: float
    gap_hours: float = 0.0


def _at(day: date, clock: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=tz)


def _date_of(stamp: int) -> date:
    return datetime.fromtimestamp(round(stamp / DAY) * DAY, UTC).date()


def _midnight(day: date) -> int:
    return int(_at(day, time(0), UTC).timestamp())


def _trading_days(first_of_month: date, market: Market) -> int:
    days = calendar.monthrange(first_of_month.year, first_of_month.month)[1]
    if market.weekdays == 7:
        return days
    return sum(
        1 for d in range(days) if (first_of_month + timedelta(days=d)).weekday() < market.weekdays
    )


def _add_months(first_of_month: date, months: int) -> date:
    index = first_of_month.month - 1 + months
    return date(first_of_month.year + index // 12, index % 12 + 1, 1)


def sub_bars(market: Market, interval: str, parent_time: int) -> tuple[SubBar, ...]:
    tz = market.tz
    overnight = 24 - market.session_hours
    day = _date_of(parent_time)

    if interval == "3mo":
        months = [_add_months(day.replace(day=1), k) for k in range(3)]
        return tuple(
            SubBar(
                _midnight(m),
                _trading_days(m, market) * market.session_hours,
                overnight if k else 0.0,
            )
            for k, m in enumerate(months)
        )

    if interval == "1wk":
        return tuple(
            SubBar(
                _midnight(day + timedelta(days=d)),
                market.session_hours,
                overnight if d else 0.0,
            )
            for d in range(market.weekdays)
        )

    if interval == "1d":
        if market.session_open is None:
            return tuple(
                SubBar(int(_at(day, time(4 * i), tz).timestamp()), 4) for i in range(6)
            )
        start = _at(day, market.session_open, tz)
        return (
            SubBar(int(start.timestamp()), 4),
            SubBar(int((start + timedelta(hours=4)).timestamp()), market.session_hours - 4),
        )

    if interval == "4h":
        if market.session_open is None:
            return tuple(SubBar(parent_time + 3600 * i, 1) for i in range(4))
        local = datetime.fromtimestamp(parent_time, tz)
        close = _at(local.date(), market.session_open, tz) + timedelta(hours=market.session_hours)
        bars = []
        start = local
        while len(bars) < 4 and start < close:
            hours = min(1.0, (close - start).total_seconds() / 3600)
            bars.append(SubBar(int(start.timestamp()), hours))
            start += timedelta(hours=1)
        return tuple(bars) or (SubBar(parent_time, 1),)

    raise ValueError(f"No lower timeframe for {interval}")
