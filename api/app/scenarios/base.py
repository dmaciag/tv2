from abc import ABC, abstractmethod
from typing import ClassVar, Literal, NamedTuple

from app.indicators.macd import MACD


class BarContext(NamedTuple):
    macd_up: bool
    histogram_up: bool
    profile: "LeanProfile"


class Anchor(NamedTuple):
    at: float
    level: Literal["high", "low"] | float
    band: tuple[float, float] | None = None


IntrabarPlan = tuple[Anchor, ...]


class Scenario(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    def plan(self, context: BarContext) -> IntrabarPlan:
        ...


class LeanProfile(NamedTuple):
    first_at: float
    lean_at: float
    hold_at: float
    hold_level: float
    band: float


LEAN_PROFILES = {
    "realistic": LeanProfile(0.20, 0.55, 0.72, 0.75, 0.50),
    "strong": LeanProfile(0.06, 0.20, 0.92, 0.92, 0.15),
    "maximum": LeanProfile(0.03, 0.10, 0.97, 0.97, 0.06),
}
DEFAULT_VARIATION = "realistic"


def lean(up: bool, profile: LeanProfile) -> IntrabarPlan:
    band = (1 - profile.band, 1.0) if up else (0.0, profile.band)
    return (
        Anchor(profile.first_at, "low" if up else "high"),
        Anchor(profile.lean_at, "high" if up else "low"),
        Anchor(profile.hold_at, profile.hold_level if up else 1 - profile.hold_level, band),
    )


class MomentumTracker:
    def __init__(self, macd: MACD | None = None):
        macd = macd or MACD()
        self.alphas = (2 / (macd.fast + 1), 2 / (macd.slow + 1), 2 / (macd.signal + 1))
        self.fast = self.slow = self.signal = None

    def context(self, fallback_up: bool, profile: LeanProfile) -> BarContext:
        if self.fast is None:
            return BarContext(fallback_up, fallback_up, profile)
        line = self.fast - self.slow
        return BarContext(line >= 0, line >= self.signal, profile)

    def update(self, close: float) -> None:
        a_fast, a_slow, a_signal = self.alphas
        if self.fast is None:
            self.fast = self.slow = close
            self.signal = 0.0
            return
        self.fast += a_fast * (close - self.fast)
        self.slow += a_slow * (close - self.slow)
        self.signal += a_signal * ((self.fast - self.slow) - self.signal)
