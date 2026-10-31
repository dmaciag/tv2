import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ChartRef, TimeRange } from '../api/chartStateApi'
import { explodeApi } from '../api/explodeApi'
import {
  EXPLODE_TO,
  EXPLODE_UNAVAILABLE,
  INTERVAL_LABELS,
  INTRADAY_TIMEFRAMES,
  VARIATIONS,
  type ExplodeResult,
  type ExplodeScenario,
  type Variation,
} from '../types/candle'
import { PriceChart, type ChartTheme, type ChartView } from './PriceChart'
import './ExplodeModal.css'

export type ExplodeState =
  | { status: 'loading'; label: string }
  | { status: 'done'; result: ExplodeResult }
  | { status: 'error'; label: string; message: string }

interface Props {
  state: ExplodeState
  variation: Variation
  onVariationChange: (variation: Variation) => void
  theme: ChartTheme
  logScale: boolean
  onClose: () => void
}

const EXACT_TOLERANCE = 1e-9

const formatDate = (time: number) => new Date(time * 1000).toISOString().slice(0, 10)

export function ExplodeModal({
  state,
  variation,
  onVariationChange,
  theme,
  logScale,
  onClose,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const result = state.status === 'done' ? state.result : null
  const parentLabel = result ? INTERVAL_LABELS[result.interval] : ''
  const subLabel = result ? INTERVAL_LABELS[result.sub_interval] : ''
  const pendingTitle =
    state.status === 'loading' ? `Exploding ${state.label}…` : state.status === 'error' ? state.label : ''

  return createPortal(
    <div className="explode-backdrop" onClick={onClose}>
      <div
        className={`explode-modal ${theme}`}
        role="dialog"
        aria-modal="true"
        aria-label="Explode scenarios"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="explode-header">
          <div className="explode-title">
            {result ? (
              <>
                <strong>
                  {result.ticker} · {parentLabel} → {subLabel}
                </strong>
                <span className="explode-meta">
                  {formatDate(result.from_time)} – {formatDate(result.to_time)} ·{' '}
                  {result.parent_bars} {parentLabel} bars exploded. Each scenario re-aggregates to
                  these exact {parentLabel} bars, so its {parentLabel} ADX and MACD are identical;
                  the {subLabel} prices and indicators are what differ.
                </span>
              </>
            ) : (
              <strong>{pendingTitle}</strong>
            )}
          </div>
          <div className="explode-variation" role="group" aria-label="Variation">
            <span>Variation</span>
            {VARIATIONS.map((v) => (
              <button
                key={v.value}
                type="button"
                className={v.value === variation ? 'active' : ''}
                aria-pressed={v.value === variation}
                disabled={state.status === 'loading'}
                onClick={() => v.value !== variation && onVariationChange(v.value)}
                title={v.hint}
              >
                {v.label}
              </button>
            ))}
          </div>
          <button type="button" className="explode-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {state.status === 'error' && <p className="explode-error">{state.message}</p>}

        {result && (
          <div className="explode-grid">
            {result.scenarios.map((scenario) => (
              <ScenarioCard
                key={`${result.variation}:${scenario.id}`}
                parent={result}
                scenario={scenario}
                theme={theme}
                logScale={logScale}
              />
            ))}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}

type Drill =
  | { status: 'loading' }
  | { status: 'done'; result: ExplodeResult }
  | { status: 'error'; message: string }

interface CardProps {
  parent: ExplodeResult
  scenario: ExplodeScenario
  theme: ChartTheme
  logScale: boolean
}

function ScenarioCard({ parent, scenario, theme, logScale }: CardProps) {
  const interval = parent.sub_interval
  const lower = EXPLODE_TO[interval]

  const [drill, setDrill] = useState<Drill | null>(null)
  const requestRef = useRef(0)
  const rangeRef = useRef<TimeRange | null>(null)
  const [ownView, setOwnView] = useState<ChartView>(() => ({
    chart: { ticker: parent.ticker, interval },
    range: { from: parent.from_time, to: scenario.candles.at(-1)?.time ?? parent.to_time },
  }))
  const [drillView, setDrillView] = useState<ChartView | null>(null)

  const handleRange = useCallback(
    (chart: ChartRef, range: TimeRange) => {
      if (chart.interval === interval) rangeRef.current = range
    },
    [interval],
  )

  function toggleDrill() {
    const request = ++requestRef.current
    if (drill) {
      setDrill(null)
      setOwnView({ chart: ownView.chart, range: rangeRef.current ?? ownView.range })
      return
    }
    const range = rangeRef.current ?? ownView.range!
    setDrill({ status: 'loading' })
    explodeApi
      .explodeCandles({
        symbol: parent.ticker,
        interval,
        candles: scenario.candles,
        from_time: Math.floor(range.from),
        to_time: Math.ceil(range.to),
        scenarios: [scenario.id],
        variation: parent.variation,
      })
      .then((result) => {
        if (request !== requestRef.current) return
        const child = result.scenarios[0]
        setDrillView({
          chart: { ticker: result.ticker, interval: result.sub_interval },
          range: { from: result.from_time, to: child.candles.at(-1)?.time ?? result.to_time },
        })
        setDrill({ status: 'done', result })
      })
      .catch(
        (err: Error) =>
          request === requestRef.current && setDrill({ status: 'error', message: err.message }),
      )
  }

  const drilled = drill?.status === 'done' ? drill.result : null
  const shown = drilled ? drilled.scenarios[0] : scenario
  const shownInterval = drilled ? drilled.sub_interval : interval
  const matchesLabel = INTERVAL_LABELS[drilled ? drilled.interval : parent.interval]
  const exact = shown.max_ohlc_error <= EXACT_TOLERANCE

  const buttonTitle = !lower
    ? (EXPLODE_UNAVAILABLE[interval] ?? 'No lower timeframe')
    : drill
      ? `Back to the ${INTERVAL_LABELS[interval]} bars`
      : `Explode these ${INTERVAL_LABELS[interval]} bars to ${INTERVAL_LABELS[lower]} with the same scenario`

  return (
    <section className="explode-card">
      <div className="explode-card-head">
        <strong>{scenario.name}</strong>
        {drilled && <span className="explode-level">{INTERVAL_LABELS[shownInterval]}</span>}
        <span
          className={exact ? 'explode-check ok' : 'explode-check'}
          title={`Largest OHLC difference after re-aggregating to ${matchesLabel}: ${shown.max_ohlc_error}`}
        >
          {exact
            ? `✓ matches ${matchesLabel}`
            : `≈ ${matchesLabel} (max diff ${shown.max_ohlc_error.toPrecision(2)})`}
        </span>
        <button
          type="button"
          className={`explode-drill ${drill ? 'active' : ''}`}
          aria-pressed={!!drill}
          disabled={!lower || drill?.status === 'loading'}
          onClick={toggleDrill}
          title={buttonTitle}
        >
          {drill?.status === 'loading'
            ? 'Exploding…'
            : lower
              ? `Explode → ${INTERVAL_LABELS[lower]}`
              : 'Explode'}
        </button>
        <span className="explode-desc">{scenario.description}</span>
        {drill?.status === 'error' && <span className="explode-drill-error">{drill.message}</span>}
      </div>
      <div className="explode-card-chart">
        <PriceChart
          candles={shown.candles}
          indicators={shown.indicators}
          view={drilled ? drillView : ownView}
          onVisibleRangeChange={handleRange}
          theme={theme}
          logScale={logScale}
          resetKey={0}
          intraday={INTRADAY_TIMEFRAMES.has(shownInterval)}
        />
      </div>
    </section>
  )
}
