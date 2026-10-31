import type { Candle, IndicatorResult } from '../types/candle'
import { request } from './request'

export const indicatorApi = {
  calculate: (candles: Candle[], indicators: string[]) =>
    request<IndicatorResult[]>('/api/indicators', {
      method: 'POST',
      body: JSON.stringify({ candles, indicators }),
    }),
}
