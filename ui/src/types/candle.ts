export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  adj_close: number
  volume: number
}

export const TIMEFRAMES = [
  { label: '1H', value: '1h' },
  { label: '4H', value: '4h' },
  { label: '1D', value: '1d' },
  { label: '1W', value: '1wk' },
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
] as const

export const INTRADAY_TIMEFRAMES: ReadonlySet<Timeframe> = new Set(['1h', '4h'])

export type Timeframe = (typeof TIMEFRAMES)[number]['value']

export const SYNTHETIC_TIMEFRAMES = [
  { label: '2H', value: '2h', base: '1h' },
  { label: '8H', value: '8h', base: '4h' },
  { label: '2D', value: '2d', base: '1d' },
  { label: '2W', value: '2wk', base: '1wk' },
  { label: '2M', value: '2mo', base: '1mo' },
  { label: '6M', value: '6mo', base: '3mo' },
] as const satisfies readonly { label: string; value: string; base: Timeframe }[]

export type SyntheticTimeframe = (typeof SYNTHETIC_TIMEFRAMES)[number]['value']

export type ChartTimeframe = Timeframe | SyntheticTimeframe

export const SYNTHETIC_BY_VALUE = Object.fromEntries(
  SYNTHETIC_TIMEFRAMES.map((tf) => [tf.value, tf]),
) as Record<SyntheticTimeframe, (typeof SYNTHETIC_TIMEFRAMES)[number]>

export function isSynthetic(tf: ChartTimeframe): tf is SyntheticTimeframe {
  return tf in SYNTHETIC_BY_VALUE
}

export const INTERVAL_LABELS = Object.fromEntries(
  TIMEFRAMES.map((tf) => [tf.value, tf.label]),
) as Record<Timeframe, string>

export const EXPLODE_TO: Partial<Record<Timeframe, Timeframe>> = {
  '3mo': '1mo',
  '1wk': '1d',
  '1d': '4h',
  '4h': '1h',
}

export const EXPLODE_UNAVAILABLE: Partial<Record<Timeframe, string>> = {
  '1mo': "Weeks straddle month boundaries, so no set of 1W bars rebuilds a month exactly",
  '1h': 'There is no lower timeframe than 1H',
}

export interface IndicatorLine {
  key: string
  label: string
  values: { time: number; value: number }[]
}

export interface IndicatorResult {
  id: string
  name: string
  params: Record<string, number>
  lines: IndicatorLine[]
}

export interface ChartData {
  ticker: string
  interval: Timeframe
  source: 'cache' | 'yfinance' | 'computed'
  fetched_at: string
  candles: Candle[]
  indicators: IndicatorResult[]
}

export interface ExplodeScenario {
  id: string
  name: string
  description: string
  candles: Candle[]
  indicators: IndicatorResult[]
  max_ohlc_error: number
}

export const VARIATIONS = [
  {
    value: 'realistic',
    label: 'Realistic',
    hint: 'Candles paced like real bars; the lower-timeframe MACDs stay fairly close',
  },
  {
    value: 'strong',
    label: 'Strong',
    hint: 'MACDs about 3x further apart; extremes come early and price holds one side, so candles step',
  },
  {
    value: 'maximum',
    label: 'Maximum',
    hint: 'MACDs as far apart as the bars allow; the first lower bar sets the whole range (clearly synthetic)',
  },
] as const

export type Variation = (typeof VARIATIONS)[number]['value']

export interface ExplodeResult {
  ticker: string
  interval: Timeframe
  sub_interval: Timeframe
  market: 'stock' | 'crypto' | 'fx'
  from_time: number
  to_time: number
  parent_bars: number
  variation: Variation
  scenarios: ExplodeScenario[]
}
