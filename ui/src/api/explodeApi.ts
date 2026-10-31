import type { Candle, ExplodeResult, Timeframe, Variation } from '../types/candle'
import type { TimeRange } from './chartStateApi'
import { request } from './request'

export const explodeApi = {
  explode: (symbol: string, interval: Timeframe, range: TimeRange, variation: Variation) =>
    request<ExplodeResult>(
      `/api/explode?${new URLSearchParams({
        symbol,
        interval,
        from_time: String(Math.floor(range.from)),
        to_time: String(Math.ceil(range.to)),
        variation,
      })}`,
    ),
  explodeCandles: (body: {
    symbol: string
    interval: Timeframe
    candles: Candle[]
    from_time: number
    to_time: number
    scenarios?: string[]
    variation: Variation
  }) =>
    request<ExplodeResult>('/api/explode/candles', { method: 'POST', body: JSON.stringify(body) }),
}
