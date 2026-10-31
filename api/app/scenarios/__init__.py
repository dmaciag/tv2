from app.scenarios.archetypes import Contrarian, MomentumChasing, MomentumFading, TrendRiding
from app.scenarios.base import MomentumTracker, Scenario

SCENARIOS: list[Scenario] = [MomentumChasing(), TrendRiding(), MomentumFading(), Contrarian()]

__all__ = ["SCENARIOS", "MomentumTracker", "Scenario"]
