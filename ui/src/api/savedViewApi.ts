import type { ChartTimeframe } from '../types/candle'
import { request } from './request'

export interface SavedViewInput {
  ticker: string
  interval: ChartTimeframe
  from: number
  to: number
}

export interface SavedView extends SavedViewInput {
  id: number
  updated_at: string
}

const BASE_URL = '/api/saved-views'

export const savedViewApi = {
  list: () => request<SavedView[]>(BASE_URL),
  save: (view: SavedViewInput) =>
    request<SavedView>(BASE_URL, { method: 'PUT', body: JSON.stringify(view) }),
  remove: (id: number) => request<void>(`${BASE_URL}/${id}`, { method: 'DELETE' }),
}
