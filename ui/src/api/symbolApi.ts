import type { ChartData, Timeframe } from '../types/candle'
import type { Symbol, SymbolCreate, SymbolUpdate } from '../types/symbol'
import { request } from './request'

const BASE_URL = '/api/symbols'

export function isFormula(input: string) {
  return /[*/()]/.test(input) || input.slice(1).includes('^')
}

export function normalizeTicker(input: string) {
  return input.replace(/\s+/g, '').toUpperCase()
}

export const symbolApi = {
  list: () => request<Symbol[]>(BASE_URL),
  get: (id: number) => request<Symbol>(`${BASE_URL}/${id}`),
  create: (data: SymbolCreate) =>
    request<Symbol>(BASE_URL, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: SymbolUpdate) =>
    request<Symbol>(`${BASE_URL}/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  remove: (id: number) => request<void>(`${BASE_URL}/${id}`, { method: 'DELETE' }),
  chart: (tickerOrFormula: string, interval: Timeframe, force: boolean) => {
    const params = { interval, force: String(force) }
    return isFormula(tickerOrFormula)
      ? request<ChartData>(
          `/api/arithmetic/chart?${new URLSearchParams({ ...params, formula: tickerOrFormula })}`,
        )
      : request<ChartData>(
          `${BASE_URL}/${encodeURIComponent(tickerOrFormula)}/chart?${new URLSearchParams(params)}`,
        )
  },
}
