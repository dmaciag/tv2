from app.scenarios.base import BarContext, Scenario, lean


class MomentumChasing(Scenario):
    id = "momentum_chasing"
    name = "Momentum chasing"
    description = (
        "Intraday traders pile in when momentum accelerates: each bar leans the way the "
        "lower-timeframe MACD histogram points."
    )

    def plan(self, context: BarContext):
        return lean(context.histogram_up, context.profile)


class TrendRiding(Scenario):
    id = "trend_riding"
    name = "Trend riding"
    description = (
        "Intraday traders stick with the lower-timeframe trend: each bar leans the way the "
        "MACD line points (above or below zero)."
    )

    def plan(self, context: BarContext):
        return lean(context.macd_up, context.profile)


class MomentumFading(Scenario):
    id = "momentum_fading"
    name = "Momentum fading"
    description = (
        "Intraday traders fade accelerating moves: each bar leans against the "
        "lower-timeframe MACD histogram."
    )

    def plan(self, context: BarContext):
        return lean(not context.histogram_up, context.profile)


class Contrarian(Scenario):
    id = "contrarian"
    name = "Contrarian"
    description = (
        "Intraday traders lean against the lower-timeframe trend: each bar leans opposite "
        "to the MACD line."
    )

    def plan(self, context: BarContext):
        return lean(not context.macd_up, context.profile)
