import type { Candle } from './candle'

export const EDGE_SHARE = 0.1

export const SHIFT_NOISE = 1.5

export interface PriceShift {
  from: number
  to: number
  factor: number
  seed: number
}

function smoothstep(x: number) {
  const t = Math.min(Math.max(x, 0), 1)
  return t * t * (3 - 2 * t)
}

function seededRandom(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), a | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function normal(random: () => number) {
  return Math.sqrt(-2 * Math.log(1 - random())) * Math.cos(2 * Math.PI * random())
}

function shiftCurve(n: number, seed: number): number[] {
  const edge = Math.max(1, n * EDGE_SHARE)
  const smooth = (p: number) => Math.min(smoothstep(p / edge), smoothstep((n - p) / edge))
  const random = seededRandom(seed)
  const steps = Array.from({ length: n }, (_, k) => smooth(k + 1) - smooth(k))
  const noisy = steps.map((s) => s + SHIFT_NOISE * Math.abs(s) * normal(random))

  for (let k = 0; k < n; ) {
    let j = k
    while (j < n && Math.sign(steps[j]) === Math.sign(steps[k])) j++
    let size = 0
    let excess = 0
    for (let i = k; i < j; i++) {
      size += Math.abs(steps[i])
      excess += noisy[i] - steps[i]
    }
    if (size > 0) for (let i = k; i < j; i++) noisy[i] -= (excess * Math.abs(steps[i])) / size
    k = j
  }

  const curve = [0]
  for (const step of noisy) curve.push(curve[curve.length - 1] + step)
  return curve
}

export function shiftCandles(candles: Candle[], shift: PriceShift): Candle[] {
  const start = candles.findIndex((c) => c.time >= shift.from)
  let end = candles.length - 1
  while (end >= 0 && candles[end].time > shift.to) end--
  if (start < 0 || end < start || shift.factor === 1) return candles

  const curve = shiftCurve(end - start + 1, shift.seed)
  const factorAt = (share: number) => shift.factor ** share

  return candles.map((c, i) => {
    if (i < start || i > end) return c
    const p = i - start
    const open = c.open * factorAt(curve[p])
    const closeFactor = factorAt(curve[p + 1])
    const close = c.close * closeFactor
    const midFactor = factorAt((curve[p] + curve[p + 1]) / 2)
    const upperWick = (c.high - Math.max(c.open, c.close)) * midFactor
    const lowerWick = (Math.min(c.open, c.close) - c.low) * midFactor
    return {
      ...c,
      open,
      close,
      adj_close: c.adj_close * closeFactor,
      high: Math.max(open, close) + upperWick,
      low: Math.min(open, close) - lowerWick,
    }
  })
}
