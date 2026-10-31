import math

from app.arithmetic.expression import Ticker, parse
from app.scenarios import SCENARIOS, MomentumTracker, Scenario
from app.scenarios.base import DEFAULT_VARIATION, LEAN_PROFILES
from app.scenarios.path import TEXTURE_SCALE, TICK_HOURS, Texture, explode_bar, layout_for
from app.scenarios.sessions import SUB_INTERVAL, market_of, sub_bars
from app.schemas.explode import ExplodeResult, ExplodeScenario
from app.schemas.indicator import IndicatorResult
from app.schemas.symbol import Candle
from app.services.arithmetic_service import ArithmeticService
from app.services.indicator_service import IndicatorService
from app.services.symbol_service import NoMarketDataError, SymbolService

WARMUP_SUB_BARS = 150
MAX_GENERATED_BARS = 50_000


class ExplodeNotSupportedError(Exception):
    pass


class TooManyBarsError(Exception):
    def __init__(self, visible: int, allowed: int):
        super().__init__(visible, allowed)
        self.visible = visible
        self.allowed = allowed


class UnknownVariationError(Exception):
    pass


class UnknownScenarioError(Exception):
    pass


class ExplodeService:
    def __init__(
        self,
        symbol_service: SymbolService,
        arithmetic_service: ArithmeticService,
        indicator_service: IndicatorService,
        scenarios: list[Scenario] = SCENARIOS,
    ):
        self.symbol_service = symbol_service
        self.arithmetic_service = arithmetic_service
        self.indicator_service = indicator_service
        self.scenarios = scenarios

    def explode(
        self,
        symbol: str,
        interval: str,
        from_time: int,
        to_time: int,
        indicator_ids: list[str],
        variation: str = DEFAULT_VARIATION,
    ) -> ExplodeResult:
        sub_interval = SUB_INTERVAL.get(interval)
        if sub_interval is None:
            raise ExplodeNotSupportedError(interval)

        node = parse(symbol)
        if isinstance(node, Ticker):
            series = self.symbol_service.get_candles(node.symbol, interval)
        else:
            series = self.arithmetic_service.get_candles(symbol, interval)
        return self.explode_candles(
            series.ticker,
            interval,
            series.candles,
            from_time,
            to_time,
            indicator_ids,
            variation=variation,
        )

    def explode_candles(
        self,
        symbol: str,
        interval: str,
        candles: list[Candle],
        from_time: int,
        to_time: int,
        indicator_ids: list[str],
        scenario_ids: list[str] | None = None,
        variation: str = DEFAULT_VARIATION,
    ) -> ExplodeResult:
        sub_interval = SUB_INTERVAL.get(interval)
        if sub_interval is None:
            raise ExplodeNotSupportedError(interval)
        profile = LEAN_PROFILES.get(variation)
        if profile is None:
            raise UnknownVariationError(variation)
        known = {s.id for s in self.scenarios}
        unknown = [s for s in scenario_ids or [] if s not in known]
        if unknown:
            raise UnknownScenarioError(", ".join(unknown))
        candles = sorted(candles, key=lambda c: c.time)

        visible = [i for i, c in enumerate(candles) if from_time <= c.time <= to_time]
        if not visible:
            raise NoMarketDataError(symbol)
        first, last = visible[0], visible[-1]

        market = market_of(parse(symbol).tickers())
        per_parent = len(sub_bars(market, interval, candles[first].time))
        running = sum(1 for s in self.scenarios if scenario_ids is None or s.id in scenario_ids)
        allowed = MAX_GENERATED_BARS // (per_parent * running)
        if len(visible) > allowed:
            raise TooManyBarsError(len(visible), allowed)
        start = max(0, first - math.ceil(WARMUP_SUB_BARS / per_parent))
        texture = Texture([c.close for c in candles])
        bars_of = {i: sub_bars(market, interval, candles[i].time) for i in range(start, last + 1)}
        tick_hours = TICK_HOURS[interval]
        texture_scale = TEXTURE_SCALE[interval]

        scenarios = []
        for variant, scenario in enumerate(self.scenarios):
            if scenario_ids is not None and scenario.id not in scenario_ids:
                continue
            momentum = MomentumTracker()
            groups = []
            for i in range(start, last + 1):
                parent = candles[i]
                group = explode_bar(
                    parent,
                    scenario,
                    momentum.context(parent.close >= parent.open, profile),
                    bars_of[i],
                    layout_for(bars_of[i], tick_hours),
                    texture,
                    texture_scale,
                    i,
                    variant,
                )
                for bar in group:
                    momentum.update(bar.close)
                groups.append(group)
            sub_candles = [bar for group in groups for bar in group]
            indicators = self.indicator_service.calculate(sub_candles, indicator_ids)

            visible_groups = groups[first - start :]
            cutoff = visible_groups[0][0].time
            error = max(
                _reaggregation_error(candles[first + j], group)
                for j, group in enumerate(visible_groups)
            )
            scenarios.append(
                ExplodeScenario(
                    id=scenario.id,
                    name=scenario.name,
                    description=scenario.description,
                    candles=[bar for bar in sub_candles if bar.time >= cutoff],
                    indicators=[_trim(ind, cutoff) for ind in indicators],
                    max_ohlc_error=error,
                )
            )

        return ExplodeResult(
            ticker=symbol,
            interval=interval,
            sub_interval=sub_interval,
            market=market.name,
            from_time=candles[first].time,
            to_time=candles[last].time,
            parent_bars=len(visible),
            variation=variation,
            scenarios=scenarios,
        )


def _reaggregation_error(parent: Candle, group: list[Candle]) -> float:
    return max(
        abs(group[0].open - parent.open),
        abs(max(b.high for b in group) - parent.high),
        abs(min(b.low for b in group) - parent.low),
        abs(group[-1].close - parent.close),
    )


def _trim(indicator: IndicatorResult, cutoff: int) -> IndicatorResult:
    return indicator.model_copy(
        update={
            "lines": [
                line.model_copy(update={"values": [p for p in line.values if p.time >= cutoff]})
                for line in indicator.lines
            ]
        }
    )
