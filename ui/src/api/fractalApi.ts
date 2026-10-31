import type { Candle } from '../types/candle'
import { request } from './request'

export interface FractalBox {
  start: number
  end: number
  low: number
  high: number
}

export interface FractalMatch {
  small: FractalBox
  big: FractalBox
  correlation: number
  time_scale: number
  price_scale: number
}

export const fractalApi = {
  find: (candles: Candle[]) =>
    request<FractalMatch>('/api/fractal', {
      method: 'POST',
      body: JSON.stringify({ candles }),
    }),
}
