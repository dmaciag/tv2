import type { Candle, Timeframe } from './candle'

const SECONDS_PER_DAY = 86_400

function barDay(time: number) {
  return Math.round(time / SECONDS_PER_DAY)
}

function barMonth(time: number) {
  const date = new Date(barDay(time) * SECONDS_PER_DAY * 1000)
  return date.getUTCFullYear() * 12 + date.getUTCMonth()
}

function groupKeys(candles: Candle[], base: Timeframe): (number | string)[] {
  switch (base) {
    case '1h':
    case '4h': {
      let day = ''
      let slot = 0
      return candles.map((c) => {
        const d = new Date(c.time * 1000).toISOString().slice(0, 10)
        slot = d === day ? slot + 1 : 0
        day = d
        return `${d}:${Math.floor(slot / 2)}`
      })
    }
    case '1d':
      return candles.map((_, i) => Math.floor(i / 2))
    case '1wk':
      return candles.map((c) => Math.floor((barDay(c.time) + 3) / 14))
    case '1mo':
      return candles.map((c) => Math.floor(barMonth(c.time) / 2))
    case '3mo':
      return candles.map((c) => Math.floor(barMonth(c.time) / 6))
  }
}

export function mergeCandles(candles: Candle[], base: Timeframe): Candle[] {
  const keys = groupKeys(candles, base)
  const merged: Candle[] = []
  candles.forEach((c, i) => {
    const bar = merged[merged.length - 1]
    if (i > 0 && keys[i] === keys[i - 1]) {
      bar.high = Math.max(bar.high, c.high)
      bar.low = Math.min(bar.low, c.low)
      bar.close = c.close
      bar.adj_close = c.adj_close
      bar.volume += c.volume
    } else {
      merged.push({ ...c })
    }
  })
  return merged
}
