import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.scenarios.base import BarContext, IntrabarPlan, Scenario
from app.scenarios.sessions import SubBar
from app.schemas.symbol import Candle


TICK_HOURS = {"4h": 1 / 12, "1d": 0.5, "1wk": 0.5, "3mo": 3.25}
GAP_TICK_WEIGHT = 0.08
TEXTURE_SCALE = {"4h": 1.0, "1d": 1.0, "1wk": 1.0, "3mo": 0.8}


@dataclass(frozen=True)
class TickLayout:
    spans: tuple[tuple[int, int], ...]
    total: int
    waypoint_ticks: np.ndarray


def layout_for(bars: tuple[SubBar, ...], tick_hours: float) -> TickLayout:
    return _layout(tuple((bar.hours, bar.gap_hours) for bar in bars), tick_hours)


@lru_cache(maxsize=256)
def _layout(shape: tuple[tuple[float, float], ...], tick_hours: float) -> TickLayout:
    spans = []
    tick = 0
    for hours, gap_hours in shape:
        if gap_hours > 0:
            tick += max(1, round(gap_hours / tick_hours * GAP_TICK_WEIGHT))
        length = max(2, round(hours / tick_hours))
        spans.append((tick, tick + length))
        tick += length
    inside = np.concatenate([np.arange(first + 1, last) for first, last in spans])
    return TickLayout(tuple(spans), tick, inside)


class Texture:
    def __init__(self, closes: list[float]):
        closes_arr = np.asarray(closes, dtype=float)
        returns = np.diff(np.log(closes_arr)) if (closes_arr > 0).all() else np.diff(closes_arr)
        returns = returns[np.isfinite(returns)]
        spread = returns.std() if len(returns) > 1 else 0.0
        self.steps = (
            np.clip((returns - returns.mean()) / spread, -4, 4) if spread > 0 else np.zeros(1)
        )

    def take(self, count: int, bar_index: int, variant: int) -> np.ndarray:
        offset = bar_index * count + variant * (len(self.steps) // 4 + 1)
        steps = np.take(self.steps, np.arange(offset, offset + count), mode="wrap")
        return steps[::-1] if variant % 2 else steps


def _path(
    open_: float,
    high: float,
    low: float,
    close: float,
    plan: IntrabarPlan,
    layout: TickLayout,
    steps: np.ndarray,
    texture_scale: float,
) -> np.ndarray:
    def value(level) -> float:
        if level == "high":
            return high
        if level == "low":
            return low
        return low + level * (high - low)

    waypoints = [
        (0, open_, None),
        *(
            (tick, value(anchor.level), anchor.band)
            for tick, anchor in _anchor_ticks(plan, layout)
        ),
        (layout.total, close, None),
    ]

    sigma = texture_scale * (high - low) / math.sqrt(layout.total)
    path = np.empty(layout.total + 1)
    for (a, va, _), (b, vb, band) in zip(waypoints, waypoints[1:]):
        frac = np.arange(b - a + 1) / (b - a)
        walk = np.concatenate([[0.0], np.cumsum(steps[a:b])])
        wiggle = (walk - frac * walk[-1]) * sigma
        lo, hi = (low, high) if band is None else (value(band[0]), value(band[1]))
        path[a : b + 1] = _reflect(va + (vb - va) * frac + wiggle, lo, hi)

    for tick, value_at, _ in waypoints:
        path[tick] = value_at
    return path


def _anchor_ticks(plan: IntrabarPlan, layout: TickLayout) -> list[tuple[int, object]]:
    candidates = layout.waypoint_ticks
    i1, i2 = [i for i, anchor in enumerate(plan) if anchor.level in ("high", "low")]
    t1, t2 = _extreme_tick(plan[i1].at, layout), _extreme_tick(plan[i2].at, layout)
    if t2 <= t1:
        later = candidates[candidates > t1]
        if len(later):
            t2 = int(later[0])
        else:
            t1 = int(candidates[candidates < t2][-1])
    ticks = {i1: t1, i2: t2}

    for i, anchor in enumerate(plan):
        if i in ticks:
            continue
        lo = max((t for j, t in ticks.items() if j < i), default=0)
        hi = min((t for j, t in ticks.items() if j > i), default=layout.total)
        room = candidates[(candidates > lo) & (candidates < hi)]
        if len(room):
            wanted = _extreme_tick(anchor.at, layout)
            ticks[i] = int(room[np.argmin(np.abs(room - wanted))])
    return [(ticks[i], plan[i]) for i in sorted(ticks, key=ticks.get)]


def _extreme_tick(at: float, layout: TickLayout) -> int:
    lengths = np.array([last - first for first, last in layout.spans], dtype=float)
    ends = np.cumsum(lengths) / lengths.sum()
    k = min(int(np.searchsorted(ends, at, side="right")), len(lengths) - 1)
    start = ends[k - 1] if k else 0.0
    within = (at - start) / (ends[k] - start)
    first, last = layout.spans[k]
    interior = np.arange(first + 1, last)
    return int(interior[round((0.2 + 0.6 * within) * (len(interior) - 1))])


def _reflect(values: np.ndarray, low: float, high: float) -> np.ndarray:
    span = high - low
    folded = np.mod(values - low, 2 * span)
    return low + np.where(folded > span, 2 * span - folded, folded)


def _split_volume(total: int, ranges: list[float]) -> list[int]:
    if total <= 0:
        return [0] * len(ranges)
    weights = np.asarray(ranges) + 0.1 * (np.mean(ranges) or 1.0)
    raw = total * weights / weights.sum()
    shares = np.floor(raw).astype(int)
    for i in np.argsort(raw - shares)[::-1][: total - shares.sum()]:
        shares[i] += 1
    return shares.tolist()


def explode_bar(
    parent: Candle,
    scenario: Scenario,
    context: BarContext,
    bars: tuple[SubBar, ...],
    layout: TickLayout,
    texture: Texture,
    texture_scale: float,
    bar_index: int,
    variant: int,
) -> list[Candle]:
    open_, close = parent.open, parent.close
    high = max(parent.high, open_, close)
    low = min(parent.low, open_, close)

    if high > low:
        plan = scenario.plan(context)
        steps = texture.take(layout.total, bar_index, variant)
        path = _path(open_, high, low, close, plan, layout, steps, texture_scale)
    else:
        path = np.full(layout.total + 1, open_)

    adj_ratio = parent.adj_close / parent.close if parent.close else 1.0
    pieces = [path[first : last + 1] for first, last in layout.spans]
    volumes = _split_volume(parent.volume, [float(p.max() - p.min()) for p in pieces])
    return [
        Candle(
            time=bar.stamp,
            open=float(piece[0]),
            high=float(piece.max()),
            low=float(piece.min()),
            close=float(piece[-1]),
            adj_close=float(piece[-1] * adj_ratio),
            volume=volume,
        )
        for bar, piece, volume in zip(bars, pieces, volumes)
    ]
