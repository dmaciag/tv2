import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { chartStateApi, type ChartRef, type TimeRange } from '../api/chartStateApi'
import { explodeApi } from '../api/explodeApi'
import { fractalApi, type FractalMatch } from '../api/fractalApi'
import { indicatorApi } from '../api/indicatorApi'
import { normalizeTicker, symbolApi } from '../api/symbolApi'
import {
  EXPLODE_TO,
  EXPLODE_UNAVAILABLE,
  INTERVAL_LABELS,
  isSynthetic,
  SYNTHETIC_BY_VALUE,
  SYNTHETIC_TIMEFRAMES,
  TIMEFRAMES,
  type Candle,
  type ChartData,
  type ChartTimeframe,
  type IndicatorResult,
  type Variation,
} from '../types/candle'
import { shiftCandles } from '../types/priceShift'
import { mergeCandles } from '../types/synthetic'
import { ExplodeModal, type ExplodeState } from './ExplodeModal'
import type { ChartPoint } from './fibPrimitive'
import { PriceChart, type ChartTheme, type ChartView } from './PriceChart'
import './ChartPanel.css'

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)')

const NO_DATA = { candles: [], indicators: [] }

const SOURCE_LABELS: Record<ChartData['source'], string> = {
  cache: 'cached',
  yfinance: 'downloaded',
  computed: 'computed',
}

const SAVE_VIEW_DELAY_MS = 500

interface Query {
  ticker: string
  timeframe: ChartTimeframe
  force: boolean
}

const chartKey = (chart: ChartRef) => `${chart.ticker}:${chart.interval}`
const syntheticKey = (ticker: string, timeframe: ChartTimeframe) => `${ticker}:${timeframe}`

const TIMEFRAME_COLUMNS = TIMEFRAMES.map((tf) => ({
  real: tf,
  synthetic: SYNTHETIC_TIMEFRAMES.find((s) => s.base === tf.value),
}))

type ChangeState =
  | { phase: 'left' }
  | { phase: 'right'; from: number }
  | { phase: 'drag'; from: number; to: number; factor: number; committed: number; seed: number }

const FIB_POINTS = 2

const RECALC_DELAY_MS = 150

type FractalState = { candles: Candle[] } & (
  | { status: 'loading' }
  | { status: 'done'; match: FractalMatch }
  | { status: 'error'; message: string }
)

interface Props {
  panelId: string
  defaultChart: ChartRef
}

export function ChartPanel({ panelId, defaultChart }: Props) {
  const [tickerInput, setTickerInput] = useState('')
  const [force, setForce] = useState(false)
  const [query, setQuery] = useState<Query | null>(null)
  const [loaded, setLoaded] = useState<{ query: Query; data: ChartData; view: ChartView } | null>(
    null,
  )
  const [failed, setFailed] = useState<{ query: Query; message: string } | null>(null)

  const [theme, setTheme] = useState<ChartTheme>(darkQuery.matches ? 'dark' : 'light')
  const [logScale, setLogScale] = useState(true)
  const [resetKey, setResetKey] = useState(0)

  const rangesRef = useRef(new Map<string, TimeRange>())
  const pendingSaveRef = useRef<{ chart: ChartRef; range: TimeRange } | null>(null)
  const saveTimerRef = useRef<number | undefined>(undefined)

  const flushViewSave = useCallback(() => {
    window.clearTimeout(saveTimerRef.current)
    const pending = pendingSaveRef.current
    pendingSaveRef.current = null
    if (pending) {
      chartStateApi
        .saveView(pending.chart.ticker, pending.chart.interval, pending.range)
        .catch(() => {})
    }
  }, [])

  const [change, setChange] = useState<ChangeState | null>(null)
  const [editedIndicators, setEditedIndicators] = useState<IndicatorResult[] | null>(null)
  const recalcRequestRef = useRef(0)

  const [fib, setFib] = useState<{ points: ChartPoint[]; hover: ChartPoint | null } | null>(null)

  const [fractal, setFractal] = useState<FractalState | null>(null)
  const fractalRequestRef = useRef(0)

  const [explode, setExplode] = useState<ExplodeState | null>(null)
  const explodeRequestRef = useRef(0)
  const [explodeVariation, setExplodeVariation] = useState<Variation>('realistic')
  const lastExplodeRef = useRef<{ chart: ChartRef; range: TimeRange } | null>(null)

  const handleVisibleRangeChange = useCallback(
    (chart: ChartRef, range: TimeRange) => {
      rangesRef.current.set(chartKey(chart), range)
      const pending = pendingSaveRef.current
      if (pending && chartKey(pending.chart) !== chartKey(chart)) flushViewSave()
      pendingSaveRef.current = { chart, range }
      window.clearTimeout(saveTimerRef.current)
      saveTimerRef.current = window.setTimeout(flushViewSave, SAVE_VIEW_DELAY_MS)
    },
    [flushViewSave],
  )

  useEffect(() => {
    window.addEventListener('pagehide', flushViewSave)
    return () => {
      window.removeEventListener('pagehide', flushViewSave)
      flushViewSave()
    }
  }, [flushViewSave])

  useEffect(() => {
    chartStateApi
      .getPanel(panelId)
      .catch(() => null)
      .then((saved) => {
        const chart = saved ?? defaultChart
        setTickerInput(chart.ticker)
        setQuery({ ticker: chart.ticker, timeframe: chart.interval, force: false })
      })
  }, [panelId, defaultChart])

  useEffect(() => {
    if (!query) return
    let stale = false
    const { timeframe: shownTimeframe } = query
    const synthetic = isSynthetic(shownTimeframe)
    const base = isSynthetic(shownTimeframe) ? SYNTHETIC_BY_VALUE[shownTimeframe].base : shownTimeframe
    const chart: ChartRef = { ticker: query.ticker, interval: base }
    const knownRange =
      rangesRef.current.get(syntheticKey(query.ticker, query.timeframe)) ??
      rangesRef.current.get(chartKey(chart))
    const loadData = symbolApi.chart(query.ticker, base, query.force).then(async (data) => {
      if (!synthetic) return data
      const candles = mergeCandles(data.candles, base)
      const ids = data.indicators.map((i) => i.id)
      return { ...data, candles, indicators: await indicatorApi.calculate(candles, ids) }
    })
    Promise.all([
      loadData,
      knownRange ?? chartStateApi.getView(chart.ticker, chart.interval).catch(() => null),
    ])
      .then(([data, range]) => {
        if (stale) return
        const shown: ChartRef = { ticker: data.ticker, interval: data.interval }
        setLoaded({ query, data, view: { chart: shown, range } })
        setChange(null)
        setEditedIndicators(null)
        setFib(null)
        if (!synthetic) chartStateApi.setPanel(panelId, shown).catch(() => {})
      })
      .catch((err: Error) => !stale && setFailed({ query, message: err.message }))
    return () => {
      stale = true
    }
  }, [query, panelId])

  const loading = !query || (loaded?.query !== query && failed?.query !== query)
  const error = query && failed?.query === query ? failed.message : null
  const { candles, indicators } = loaded?.data ?? NO_DATA
  const timeframe = query?.timeframe ?? defaultChart.interval

  const shownCandles = useMemo(
    () => (change?.phase === 'drag' ? shiftCandles(candles, change) : candles),
    [candles, change],
  )
  const edited = shownCandles !== candles
  const shownIndicators = edited ? (editedIndicators ?? indicators) : indicators

  useEffect(() => {
    if (!edited) return
    const request = ++recalcRequestRef.current
    const ids = indicators.map((i) => i.id)
    const timer = window.setTimeout(() => {
      indicatorApi
        .calculate(shownCandles, ids)
        .then((result) => request === recalcRequestRef.current && setEditedIndicators(result))
        .catch(() => {})
    }, RECALC_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [edited, shownCandles, indicators])

  function startChange() {
    recalcRequestRef.current++
    setEditedIndicators(null)
    setChange({ phase: 'left' })
    if (fibPicking) setFib(null)
  }

  const fibPicking = !!fib && fib.points.length < FIB_POINTS
  const fibPoints = useMemo(
    () => (fib?.hover && fibPicking ? [...fib.points, fib.hover] : (fib?.points ?? [])),
    [fib, fibPicking],
  )
  const fibHint = !fib
    ? null
    : ['Fib: click the top', 'Fib: click the bottom', 'Fib: click Fib again to clear'][
        fib.points.length
      ]

  function handleFib() {
    if (fib) {
      setFib(null)
      return
    }
    if (change && change.phase !== 'drag') clearChange()
    setFib({ points: [], hover: null })
  }

  const pickFibPoint = useCallback((point: ChartPoint) => {
    setFib((f) =>
      f && f.points.length < FIB_POINTS ? { points: [...f.points, point], hover: null } : f,
    )
  }, [])

  const hoverFibPoint = useCallback((point: ChartPoint | null) => {
    setFib((f) =>
      f && f.points.length > 0 && f.points.length < FIB_POINTS ? { ...f, hover: point } : f,
    )
  }, [])

  function clearChange() {
    recalcRequestRef.current++
    setEditedIndicators(null)
    setChange(null)
  }

  const pickChangeEdge = useCallback((time: number) => {
    setChange((c) => {
      if (c?.phase === 'left') return { phase: 'right', from: time }
      if (c?.phase === 'right') {
        const [from, to] = c.from <= time ? [c.from, time] : [time, c.from]
        const seed = Math.floor(Math.random() * 2 ** 32)
        return { phase: 'drag', from, to, factor: 1, committed: 1, seed }
      }
      return c
    })
  }, [])

  const dragChange = useCallback((ratio: number, done: boolean) => {
    setChange((c) => {
      if (c?.phase !== 'drag') return c
      const factor = c.committed * ratio
      return { ...c, factor, committed: done ? factor : c.committed }
    })
  }, [])

  const changeBand =
    change?.phase === 'right'
      ? { from: change.from, to: null }
      : change?.phase === 'drag'
        ? { from: change.from, to: change.to }
        : null
  const changeHint =
    change?.phase === 'left'
      ? 'Change: click the left edge'
      : change?.phase === 'right'
        ? 'Change: click the right edge'
        : change?.phase === 'drag'
          ? `Change: drag the price pane up or down · ${change.factor >= 1 ? '+' : ''}${((change.factor - 1) * 100).toFixed(2)}%`
          : null

  const shownFractal = fractal?.candles === shownCandles ? fractal : null
  const fractalBoxes = useMemo(() => {
    if (shownFractal?.status !== 'done') return undefined
    const { small, big, time_scale, price_scale } = shownFractal.match
    return [
      { ...small, label: 'Small' },
      { ...big, label: `Big · ${time_scale.toFixed(1)}× longer · ${price_scale.toFixed(1)}× the move` },
    ]
  }, [shownFractal])
  const fractalHint =
    shownFractal?.status === 'loading'
      ? 'Fractal: searching the visible bars…'
      : shownFractal?.status === 'done'
        ? `Fractal: ${(shownFractal.match.correlation * 100).toFixed(0)}% shape match`
        : shownFractal?.status === 'error'
          ? `Fractal: ${shownFractal.message}`
          : null

  function handleFractal() {
    const request = ++fractalRequestRef.current
    if (shownFractal) {
      setFractal(null)
      return
    }
    const range = loaded && rangesRef.current.get(
      shownSynthetic
        ? syntheticKey(loaded.query.ticker, shownSynthetic.value)
        : chartKey(loaded.view.chart),
    )
    const bars = shownCandles
    const visible = range ? bars.filter((c) => c.time >= range.from && c.time <= range.to) : bars
    setFractal({ candles: bars, status: 'loading' })
    fractalApi
      .find(visible.length > 0 ? visible : bars)
      .then(
        (match) =>
          request === fractalRequestRef.current && setFractal({ candles: bars, status: 'done', match }),
      )
      .catch(
        (err: Error) =>
          request === fractalRequestRef.current &&
          setFractal({ candles: bars, status: 'error', message: err.message }),
      )
  }

  function runExplode(chart: ChartRef, range: TimeRange, variation: Variation) {
    const target = EXPLODE_TO[chart.interval]
    if (!target) return
    lastExplodeRef.current = { chart, range }
    const label = `${chart.ticker} ${INTERVAL_LABELS[chart.interval]} → ${INTERVAL_LABELS[target]}`
    const request = ++explodeRequestRef.current
    setExplode({ status: 'loading', label })
    explodeApi
      .explode(chart.ticker, chart.interval, range, variation)
      .then((result) => request === explodeRequestRef.current && setExplode({ status: 'done', result }))
      .catch(
        (err: Error) =>
          request === explodeRequestRef.current &&
          setExplode({ status: 'error', label, message: err.message }),
      )
  }

  function handleExplode() {
    if (!loaded || candles.length === 0) return
    const { chart } = loaded.view
    const range = rangesRef.current.get(chartKey(chart)) ?? {
      from: candles[0].time,
      to: candles[candles.length - 1].time,
    }
    runExplode(chart, range, explodeVariation)
  }

  function changeExplodeVariation(variation: Variation) {
    setExplodeVariation(variation)
    const last = lastExplodeRef.current
    if (last) runExplode(last.chart, last.range, variation)
  }

  const closeExplode = useCallback(() => {
    explodeRequestRef.current++
    setExplode(null)
  }, [])

  const shownInterval = loaded?.view.chart.interval
  const shownSynthetic =
    loaded && isSynthetic(loaded.query.timeframe) ? SYNTHETIC_BY_VALUE[loaded.query.timeframe] : null
  const explodeTarget = !shownSynthetic && shownInterval && EXPLODE_TO[shownInterval]
  const explodeTitle = !shownInterval
    ? 'Load a chart first'
    : shownSynthetic
      ? `Explode isn't available on synthetic timeframes (${shownSynthetic.label} is built from ${INTERVAL_LABELS[shownSynthetic.base]} bars in the browser)`
      : explodeTarget
        ? `Show 4 ${INTERVAL_LABELS[explodeTarget]} scenarios that rebuild exactly the visible ${INTERVAL_LABELS[shownInterval]} bars`
        : EXPLODE_UNAVAILABLE[shownInterval] ?? 'Not available for this timeframe'

  const handleRangeChange = shownSynthetic
    ? (chart: ChartRef, range: TimeRange) =>
        rangesRef.current.set(syntheticKey(chart.ticker, shownSynthetic.value), range)
    : handleVisibleRangeChange

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const ticker = normalizeTicker(tickerInput)
    if (ticker) setQuery({ ticker, timeframe, force })
  }

  const last = shownCandles.at(-1)
  const prev = shownCandles.at(-2)
  const lastChange = last && prev ? ((last.close - prev.close) / prev.close) * 100 : null

  return (
    <section className={`chart-panel ${theme}`}>
      <form className="chart-toolbar" onSubmit={handleSubmit}>
        <input
          className="ticker-input"
          placeholder="Ticker or formula, e.g. AAPL or TTD/(AAPL^0.5*MSFT^0.5)"
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value)}
          aria-label="Ticker"
        />
        {}
        <div className="timeframes" role="group" aria-label="Timeframe">
          {TIMEFRAME_COLUMNS.flatMap(({ real, synthetic }, column) =>
            [synthetic, real].map(
              (tf, row) =>
                tf && (
                  <button
                    key={tf.value}
                    type="button"
                    className={`${row === 0 ? 'synthetic' : ''} ${tf.value === timeframe ? 'active' : ''}`}
                    style={{ gridRow: row + 1, gridColumn: column + 1 }}
                    aria-pressed={tf.value === timeframe}
                    disabled={!query}
                    title={
                      'base' in tf
                        ? `Synthetic: pairs of ${INTERVAL_LABELS[tf.base]} bars merged in the browser. Not cached or saved; Explode is off.`
                        : undefined
                    }
                    onClick={() => query && setQuery({ ...query, timeframe: tf.value, force })}
                  >
                    {tf.label}
                  </button>
                ),
            ),
          )}
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Loading…' : 'Load'}
        </button>
        <label className="force-toggle" title="Re-download from yfinance instead of using the JSON cache">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
          Force
        </label>

        <span className="toolbar-spacer" />

        <button
          type="button"
          className={change ? 'active' : ''}
          onClick={startChange}
          disabled={candles.length === 0}
          title="Pick a left and right bar, then drag that span up or down to see the indicators on the new prices. Temporary: nothing is saved."
        >
          Change
        </button>
        {change && (
          <button type="button" onClick={clearChange} title="Undo the change and show the real prices">
            Clear
          </button>
        )}
        <button
          type="button"
          className={fib ? 'active' : ''}
          onClick={handleFib}
          disabled={candles.length === 0}
          title="Draw Fibonacci levels: click the top, then the bottom. 0 is the bottom, 1 the top, and the levels continue above it. Click again to clear."
        >
          Fib
        </button>
        <button
          type="button"
          className={shownFractal ? 'active' : ''}
          onClick={handleFractal}
          disabled={candles.length === 0}
          title="Find a pattern in the visible bars that repeats at a larger scale, boxed in yellow. Click again to clear."
        >
          Fractal
        </button>
        <button
          type="button"
          onClick={handleExplode}
          disabled={!explodeTarget || candles.length === 0}
          title={explodeTitle}
        >
          Explode
        </button>

        <button
          type="button"
          className={logScale ? 'active' : ''}
          onClick={() => setLogScale((v) => !v)}
          title="Logarithmic price scale"
        >
          Log
        </button>
        <button type="button" onClick={() => setResetKey((k) => k + 1)} title="Fit all data">
          Reset
        </button>
        <button
          type="button"
          onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          title="Toggle dark mode"
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </form>

      {loaded && last && (
        <div className="chart-legend">
          <strong>{loaded.data.ticker}</strong>
          <span>
            {shownSynthetic
              ? `${shownSynthetic.label} (synthetic)`
              : TIMEFRAMES.find((tf) => tf.value === loaded.data.interval)?.label}
          </span>
          <span>{last.close.toFixed(2)}</span>
          {lastChange !== null && (
            <span className={lastChange >= 0 ? 'up' : 'down'}>
              {lastChange >= 0 ? '+' : ''}
              {lastChange.toFixed(2)}%
            </span>
          )}
          {changeHint && <span className="change-hint">{changeHint}</span>}
          {fibHint && <span className="change-hint">{fibHint}</span>}
          {fractalHint && <span className="fractal-hint">{fractalHint}</span>}
          <span className="chart-source">
            {SOURCE_LABELS[loaded.data.source]}{' '}
            {new Date(loaded.data.fetched_at).toLocaleString()}
          </span>
        </div>
      )}

      {error && <p className="chart-error">{error}</p>}

      <PriceChart
        crosshairSyncId={panelId}
        candles={shownCandles}
        indicators={shownIndicators}
        view={loaded?.view ?? null}
        changeBand={changeBand}
        boxes={fractalBoxes}
        fibPoints={fibPoints}
        onPickPoint={fibPicking ? pickFibPoint : undefined}
        onHoverPoint={fibPicking && fib.points.length > 0 ? hoverFibPoint : undefined}
        onPickTime={change?.phase === 'left' || change?.phase === 'right' ? pickChangeEdge : undefined}
        onDragPrice={change?.phase === 'drag' ? dragChange : undefined}
        onVisibleRangeChange={handleRangeChange}
        theme={theme}
        logScale={logScale}
        resetKey={resetKey}
      />

      {explode && (
        <ExplodeModal
          state={explode}
          variation={explodeVariation}
          onVariationChange={changeExplodeVariation}
          theme={theme}
          logScale={logScale}
          onClose={closeExplode}
        />
      )}
    </section>
  )
}
