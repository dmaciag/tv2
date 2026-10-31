import type { Timeframe } from '../types/candle'
import { HttpError, request } from './request'

export interface ChartRef {
  ticker: string
  interval: Timeframe
}

export interface TimeRange {
  from: number
  to: number
}

const BASE_URL = '/api/chart-state'

function orNull<T>(promise: Promise<T>): Promise<T | null> {
  return promise.catch((err) => {
    if (err instanceof HttpError && err.status === 404) return null
    throw err
  })
}

function viewUrl(ticker: string, interval: Timeframe) {
  return `${BASE_URL}/views?${new URLSearchParams({ ticker, interval })}`
}

export const chartStateApi = {
  getPanel: (panel: string) => orNull(request<ChartRef>(`${BASE_URL}/panels/${panel}`)),
  setPanel: (panel: string, ref: ChartRef) =>
    request<ChartRef>(`${BASE_URL}/panels/${panel}`, { method: 'PUT', body: JSON.stringify(ref) }),
  getView: (ticker: string, interval: Timeframe) =>
    orNull(request<TimeRange>(viewUrl(ticker, interval))),
  saveView: (ticker: string, interval: Timeframe, range: TimeRange) =>
    request<TimeRange>(viewUrl(ticker, interval), {
      method: 'PUT',
      body: JSON.stringify(range),
      keepalive: true,
    }),
}
